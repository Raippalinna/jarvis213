"""Offline invariants. Every network boundary uses a fake, never a live credential."""
import asyncio
import importlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from langchain_core.messages import HumanMessage
from jarvis.safety import guard
from jarvis.safety.secrets import contains_secret, redact
from jarvis.memory.access import MemoryScope
from jarvis.memory.store import MemoryStore
from jarvis.memory.context import build_context
from jarvis.approval.gate import ApprovalGate
from jarvis.notify import sinks
from jarvis.routing.providers import ProviderCatalog
from jarvis.routing.tiers import Tier, Sensitivity, TierRouter, NoEligibleRoute, eligibility_reason
from jarvis.routing.perplexity import ROUTER_BASE_URL, sek_per_1k
from scripts.perplexity_preflight import fetch_catalog
from test_reliability import state, response

supervisor = importlib.import_module("jarvis.core.supervisor")
cloud = importlib.import_module("jarvis_cloud")
audit = importlib.import_module("jarvis.audit.monthly_report")
TENANT = "00000000-0000-0000-0000-000000000011"
USER = "00000000-0000-0000-0000-000000000022"
OTHER = "00000000-0000-0000-0000-000000000033"


def http_response(payload):
    manager = MagicMock()
    manager.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    manager.__enter__.return_value.status = 200
    return manager


def completion_manager(responses):
    complete = AsyncMock(side_effect=responses)
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=complete))))
    manager.__aexit__ = AsyncMock(return_value=False)
    return manager, complete


class SwitchTests(unittest.TestCase):
    def test_missing_credentials_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen") as net:
            self.assertFalse(guard.check_autonomy().allowed)
            net.assert_not_called()

    def test_exact_enabled_value_only(self):
        for rows, allowed in [
            ([{"value": "true"}], True), ([{"value": "false"}], False),
            ([{"value": "TRUE"}], False), ([{"value": 1}], False), ([], False),
            ([{"value": "true"}, {"value": "true"}], False), ({"value": "true"}, False),
        ]:
            with self.subTest(rows=rows), patch.dict(os.environ, {}, clear=True):
                with patch("urllib.request.urlopen", return_value=http_response(rows)):
                    result = guard.check_autonomy(supabase_url="https://unit.invalid",
                                                  supabase_key="offline-placeholder")
                    self.assertEqual(result.allowed, allowed)

    def test_network_error_fails_closed_without_secret_details(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "urllib.request.urlopen", side_effect=RuntimeError("DO_NOT_LEAK")
        ):
            result = guard.check_autonomy(supabase_url="https://unit.invalid",
                                          supabase_key="offline-placeholder")
            self.assertFalse(result.allowed)
            self.assertNotIn("DO_NOT_LEAK", str(result))

    def test_no_cached_true_after_flag_changes(self):
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen", side_effect=[
            http_response([{"value": "true"}]), http_response([{"value": "false"}])
        ]) as net:
            kw = dict(supabase_url="https://unit.invalid", supabase_key="offline-placeholder")
            guard.require_autonomy("first", **kw)
            with self.assertRaises(guard.SafetyStop):
                guard.require_autonomy("second", **kw)
            self.assertEqual(net.call_count, 2)

    def test_dry_run_prevents_even_switch_lookup(self):
        with patch.dict(os.environ, {"JARVIS_DRY_RUN": "1"}, clear=True):
            with patch("urllib.request.urlopen") as net:
                self.assertEqual(guard.check_autonomy().reason, "dry_run")
                net.assert_not_called()

    def test_graph_stop_has_no_downstream_calls(self):
        with patch.object(guard, "check_autonomy", return_value=guard.GuardDecision(False, "disabled")):
            with patch.object(supervisor, "_approval") as approvals, \
                 patch.object(supervisor, "build_context") as memory, \
                 patch.object(supervisor, "AsyncOpenAI") as provider, \
                 patch.object(supervisor, "notify_all") as notify:
                result = asyncio.run(supervisor.Supervisor().chat([HumanMessage(content="Hej")]))
                self.assertEqual(cloud._execution_status(result), "paused")
                for mock in (approvals, memory, provider, notify):
                    mock.assert_not_called()

    def test_every_write_boundary_blocks_when_switch_disabled(self):
        env = {"NOTION_TOKEN": "offline-placeholder", "SUPABASE_URL": "https://unit.invalid",
               "SUPABASE_SERVICE_ROLE_KEY": "offline-placeholder",
               "SLACK_WEBHOOK_URL": "https://unit.invalid/hook"}
        with patch.dict(os.environ, env, clear=True), patch.object(
            guard, "check_autonomy", return_value=guard.GuardDecision(False, "disabled")
        ), patch("urllib.request.urlopen") as net:
            self.assertIn("blocked", sinks._post("https://unit.invalid", {}, {}))
            self.assertIsNone(MemoryStore().upsert(
                "internal note", "conversation", scope=MemoryScope(TENANT, USER)))
            self.assertIsNone(ApprovalGate()._insert("approval_audit_log", {}))
            self.assertIn("blocked", cloud._post_to_notion_page("page", "task", "answer", {}))
            self.assertEqual(audit.main(), 4)
            net.assert_not_called()

    def test_provider_rechecks_switch_between_fallbacks(self):
        manager, complete = completion_manager([response(""), response("must not run")])
        with patch.dict(os.environ, {"COMET_API_KEY": "offline-placeholder"}, clear=True), \
             patch.object(supervisor, "AsyncOpenAI", return_value=manager), \
             patch.object(guard, "require_autonomy", side_effect=[
                 None, guard.SafetyStop("model_call", "disabled")
             ]):
            result = asyncio.run(supervisor.execute(state()))
        self.assertEqual(complete.await_count, 1)
        self.assertEqual(result["frugality"]["execution_status"], "paused")


class BudgetTests(unittest.TestCase):
    def test_budget_veto_cannot_escalate_for_private_data(self):
        with patch.dict(os.environ, {"COMET_API_KEY": "offline-placeholder"}, clear=True):
            router = TierRouter(ProviderCatalog())
            for sensitivity in (Sensitivity.INTERNAL, Sensitivity.CONFIDENTIAL, Sensitivity.SECRET):
                with self.subTest(sensitivity=sensitivity), self.assertRaises(NoEligibleRoute) as ctx:
                    router.choose(Tier.HIGH, sensitivity=sensitivity, month_spend_pct=99)
                self.assertEqual(ctx.exception.status, "budget_blocked")

    def test_free_never_uses_paid_last_resort(self):
        with patch.dict(os.environ, {"COMET_API_KEY": "offline-placeholder"}, clear=True):
            with self.assertRaises(NoEligibleRoute):
                TierRouter(ProviderCatalog()).choose(
                    Tier.FREE, sensitivity=Sensitivity.PUBLIC, month_spend_pct=0)

    def test_missing_or_invalid_budget_is_not_zero(self):
        router = TierRouter(ProviderCatalog())
        for spend in (None, float("nan"), float("inf"), -1):
            with self.subTest(spend=spend), self.assertRaises(NoEligibleRoute) as ctx:
                router.choose(Tier.MED, month_spend_pct=spend)
            self.assertEqual(ctx.exception.status, "budget_unavailable")

    def test_no_credentials_means_no_route_not_last_resort(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(NoEligibleRoute):
            TierRouter(ProviderCatalog()).choose(Tier.MED, month_spend_pct=0)

    def test_low_works_without_lowering_floor(self):
        with patch.dict(os.environ, {"COMET_API_KEY": "offline-placeholder"}, clear=True):
            catalog = ProviderCatalog()
            route = TierRouter(catalog).choose(Tier.LOW, month_spend_pct=0)
            self.assertEqual(route.model_id, "gpt-4o")
            self.assertEqual(catalog.tiers["LOW"]["quality_floor"], 0.75)

    def test_all_preflight_choices_pass_same_runtime_predicate(self):
        env = {"COMET_API_KEY": "offline-placeholder", "CEREBRAS_API_KEY": "offline-placeholder"}
        with patch.dict(os.environ, env, clear=True):
            catalog = ProviderCatalog()
            for tier in Tier:
                sensitivity = Sensitivity.PUBLIC if tier == Tier.FREE else Sensitivity.INTERNAL
                route = TierRouter(catalog).choose(tier, sensitivity=sensitivity, month_spend_pct=0)
                self.assertEqual(eligibility_reason(
                    route.provider, route.model_id, catalog.tiers[route.tier.value],
                    sensitivity, 800, 800, free_only=tier == Tier.FREE), "")

    def test_fallback_reserves_unknown_timeout_cost(self):
        manager, complete = completion_manager([TimeoutError("offline")])
        with patch.dict(os.environ, {"COMET_API_KEY": "offline-placeholder"}, clear=True), \
             patch.object(guard, "require_autonomy"), \
             patch.object(supervisor, "AsyncOpenAI", return_value=manager), \
             patch.dict(supervisor._catalog.tiers["MED"], {"max_cost_per_call_sek": 0.2}):
            result = asyncio.run(supervisor.execute(state()))
        self.assertEqual(complete.await_count, 1)
        self.assertTrue(result["frugality"]["unreconciled_cost"])
        self.assertGreater(result["frugality"]["reserved_cost_sek"], 0)

    def test_preflight_missing_meter_blocks_model(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(supervisor, "AsyncOpenAI") as api:
            result = asyncio.run(supervisor.frugality_preflight(state()))
            result = asyncio.run(supervisor.execute(result))
            api.assert_not_called()
            self.assertEqual(result["frugality"]["execution_status"], "budget_unavailable")


class MemoryTests(unittest.TestCase):
    def test_reflection_preserves_retrieved_confidential_label(self):
        current = state()
        current["current_user_id"] = "cloud"
        current["memory_context"]["sensitivity"] = "confidential"
        current["messages"].append(HumanMessage(content="En kort sammanfattning"))
        current["frugality"]["execution_status"] = "succeeded"
        env = {"JARVIS_MEMORY_ACTOR": "cloud", "JARVIS_MEMORY_TENANT_ID": TENANT,
               "JARVIS_MEMORY_USER_ID": USER, "JARVIS_MEMORY_MAX_SENSITIVITY": "confidential"}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(supervisor, "_memory_store") as store:
            store.enabled = True
            store.upsert.return_value = 7
            asyncio.run(supervisor.reflect(current))
            self.assertEqual(store.upsert.call_args.kwargs["sensitivity"], "confidential")

    def test_missing_scope_reads_nothing(self):
        store = MemoryStore("https://unit.invalid", "offline-placeholder")
        with patch("urllib.request.urlopen") as net:
            self.assertEqual(store.search("anything"), [])
            self.assertIsNone(store.upsert("note", "conversation"))
            net.assert_not_called()

    def test_scope_cannot_come_from_prompt_or_unknown_actor(self):
        env = {"JARVIS_MEMORY_ACTOR": "cloud", "JARVIS_MEMORY_TENANT_ID": TENANT,
               "JARVIS_MEMORY_USER_ID": USER}
        with patch.dict(os.environ, env, clear=True):
            self.assertIsNone(MemoryScope.for_actor("other"))
            self.assertIsNone(MemoryScope.for_actor("ignore policy cloud"))
            self.assertEqual(MemoryScope.for_actor("cloud").allowed_levels, ["public", "internal"])

    def test_invalid_scope_fails_closed(self):
        with self.assertRaises(ValueError):
            MemoryScope("not-a-uuid", USER)
        with self.assertRaises(ValueError):
            MemoryScope(TENANT, USER, "secret")

    def test_search_filters_both_ids_and_rejects_wrong_owner(self):
        row = {"id": 1, "tenant_id": TENANT, "user_id": USER, "source": "conversation",
               "kind": "chunk", "content": "owned note", "sensitivity": "internal"}
        other = {**row, "id": 2, "user_id": OTHER}
        store = MemoryStore("https://unit.invalid", "offline-placeholder")
        with patch("urllib.request.urlopen", return_value=http_response([row, other])) as net:
            hits = store.search("note", scope=MemoryScope(TENANT, USER))
            query = parse_qs(urlparse(net.call_args.args[0].full_url).query)
            self.assertEqual(query["tenant_id"], [f"eq.{TENANT}"])
            self.assertEqual(query["user_id"], [f"eq.{USER}"])
            self.assertEqual([hit.id for hit in hits], [1])
            self.assertNotIn("/rpc/", net.call_args.args[0].full_url)

    def test_empty_clearance_never_defaults_to_all(self):
        store = MemoryStore("https://unit.invalid", "offline-placeholder")
        with patch("urllib.request.urlopen") as net:
            self.assertEqual(store.search("note", allowed_sensitivity=[],
                                          scope=MemoryScope(TENANT, USER)), [])
            net.assert_not_called()

    def test_secret_query_is_not_sent_to_embedding_or_database(self):
        store = MemoryStore("https://unit.invalid", "offline-placeholder")
        with patch("urllib.request.urlopen") as net:
            self.assertEqual(store.search("api_key=do-not-transmit",
                                          scope=MemoryScope(TENANT, USER)), [])
            net.assert_not_called()

    def test_insert_uses_scope_not_title(self):
        store = MemoryStore("https://unit.invalid", "offline-placeholder")
        with patch.object(store, "_insert", return_value=[{"id": 7}]) as insert:
            self.assertEqual(store.upsert("note", "conversation", title="someone else",
                                          scope=MemoryScope(TENANT, USER)), 7)
            self.assertEqual(insert.call_args.args[0]["tenant_id"], TENANT)
            self.assertEqual(insert.call_args.args[0]["user_id"], USER)

    def test_no_scope_skips_every_memory_layer(self):
        with patch("jarvis.memory.context.MemoryStore") as store, \
             patch("jarvis.memory.context.NotionControlRoom") as notion, \
             patch("jarvis.memory.context.WikiReader") as wiki:
            self.assertEqual(build_context("question").text, "")
            for mock in (store, notion, wiki):
                mock.assert_not_called()

    def test_unclassified_shared_context_not_available_to_internal_scope(self):
        with patch("jarvis.memory.context.MemoryStore") as store, \
             patch("jarvis.memory.context.NotionControlRoom") as notion, \
             patch("jarvis.memory.context.WikiReader") as wiki:
            store.return_value.search.return_value = []
            build_context("question", scope=MemoryScope(TENANT, USER, shared_context=True))
            notion.return_value.brief.assert_not_called()
            wiki.return_value.brief.assert_not_called()

    def test_topic_words_do_not_widen_clearance(self):
        env = {"JARVIS_MEMORY_ACTOR": "cloud", "JARVIS_MEMORY_TENANT_ID": TENANT,
               "JARVIS_MEMORY_USER_ID": USER}
        bundle = SimpleNamespace(text="", sources_used=[], hits_vector=0, hits_wiki=0,
                                 notion_used=False, sensitivity="public")
        current = state()
        current["current_user_id"] = "cloud"
        current["messages"] = [HumanMessage(content="hemlig avtal personnummer")]
        with patch.dict(os.environ, env, clear=True), \
             patch.object(supervisor, "build_context", return_value=bundle) as context:
            asyncio.run(supervisor.load_memory(current))
            self.assertEqual(context.call_args.kwargs["scope"].max_sensitivity, "internal")


class RouterTests(unittest.TestCase):
    def test_proxy_preflight_does_not_put_key_in_command(self):
        payload = {"data": [{"id": "test/model", "pricing": {
            "input": 1, "output": 2, "unit": "usd_per_1m_tokens"}}]}
        result = SimpleNamespace(returncode=0, stdout=json.dumps(payload) + "\n200")
        with patch("scripts.perplexity_preflight.subprocess.run", return_value=result) as run:
            snapshot = fetch_catalog(proxy_credential=True)
            self.assertEqual(snapshot["data"][0]["id"], "test/model")
            self.assertNotIn("Authorization", str(run.call_args))
            self.assertNotIn("/chat/completions", str(run.call_args))

    def test_proxy_preflight_reports_401_without_body(self):
        import urllib.error
        result = SimpleNamespace(returncode=0, stdout='{"error":"do-not-echo"}\n401')
        with patch("scripts.perplexity_preflight.subprocess.run", return_value=result):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                fetch_catalog(proxy_credential=True)
            self.assertEqual(ctx.exception.code, 401)
            self.assertNotIn("do-not-echo", str(ctx.exception))
            ctx.exception.close()

    def test_router_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            catalog = ProviderCatalog()
            self.assertEqual(catalog.integration_status["perplexity_router"], "disabled")
            self.assertNotIn("perplexity_router", catalog.providers)

    def test_opt_in_without_configuration_does_not_register(self):
        with patch.dict(os.environ, {"JARVIS_ENABLE_PERPLEXITY": "1"}, clear=True):
            catalog = ProviderCatalog()
            self.assertEqual(catalog.integration_status["perplexity_router"], "configuration_blocked")
            self.assertNotIn("perplexity_router", catalog.providers)

    def test_price_unit_conversion(self):
        self.assertAlmostEqual(sek_per_1k(3, 10), 0.03)
        for price, fx in [(-1, 10), (1, 0), (float("nan"), 10), (1, float("inf"))]:
            with self.subTest(price=price, fx=fx), self.assertRaises(ValueError):
                sek_per_1k(price, fx)

    def router_fixture(self, directory):
        path = Path(directory) / "catalog.json"
        snapshot = {"base_url": ROUTER_BASE_URL,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "data": [{"id": "test/offline-model", "pricing": {
                        "input": 1, "output": 2, "unit": "usd_per_1m_tokens"}}]}
        path.write_text(json.dumps(snapshot))
        return snapshot, path, {
            "JARVIS_ENABLE_PERPLEXITY": "1", "JARVIS_ROUTER_DATA_APPROVED": "1",
            "JARVIS_PERPLEXITY_MODEL": "test/offline-model", "JARVIS_ROUTER_TIER": "MED",
            "JARVIS_ROUTER_QUALITY_INDEX": "0.9", "JARVIS_ROUTER_USD_SEK": "10",
            "JARVIS_ROUTER_MODELS_PATH": str(path), "PERPLEXITY_API_KEY": "offline-placeholder",
        }

    def test_verified_fixture_model_can_be_registered_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, env = self.router_fixture(directory)
            with patch.dict(os.environ, env, clear=True), patch("urllib.request.urlopen") as net:
                catalog = ProviderCatalog()
                route = TierRouter(catalog).choose(Tier.MED, month_spend_pct=0)
                self.assertEqual(route.provider.key, "perplexity_router")
                self.assertEqual(route.model_id, "test/offline-model")
                net.assert_not_called()

    def test_stale_catalog_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot, path, env = self.router_fixture(directory)
            snapshot["fetched_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            path.write_text(json.dumps(snapshot))
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(ProviderCatalog().integration_status["perplexity_router"],
                                 "configuration_blocked")

    def test_unknown_model_is_not_substituted(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, env = self.router_fixture(directory)
            env["JARVIS_PERPLEXITY_MODEL"] = "test/not-in-catalog"
            with patch.dict(os.environ, env, clear=True):
                self.assertNotIn("perplexity_router", ProviderCatalog().providers)

    def test_router_cannot_receive_confidential_data(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, env = self.router_fixture(directory)
            with patch.dict(os.environ, env, clear=True), self.assertRaises(NoEligibleRoute):
                TierRouter(ProviderCatalog()).choose(
                    Tier.MED, sensitivity=Sensitivity.CONFIDENTIAL, month_spend_pct=0)


class BoundaryTests(unittest.TestCase):
    def test_notification_flag_applies_to_direct_monthly_sinks(self):
        with patch.dict(os.environ, {"JARVIS_NOTIFY": "0"}, clear=True), \
             patch.object(sinks, "_post") as post:
            self.assertEqual(sinks._slack_send("a", "b"), "disabled")
            self.assertEqual(sinks._notion_append("a", "b"), "disabled")
            post.assert_not_called()

    def test_redacts_common_credentials_but_not_normal_uuid(self):
        for text in ["password=not-for-logs", "api_key=not-for-logs",
                     "sk-" + "a" * 24, "ghp_" + "b" * 24, "sb_secret_" + "c" * 24]:
            self.assertTrue(contains_secret(text))
            self.assertNotIn(text, redact(text))
        self.assertEqual(redact(TENANT), TENANT)

    def test_notion_notification_uses_patch(self):
        with patch.dict(os.environ, {"NOTION_TOKEN": "ntn_offline", "NOTION_LOG_PAGE_ID": "page"}):
            with patch.object(sinks, "_post", return_value="ok") as post:
                sinks._notion_append("title", "body")
                self.assertEqual(post.call_args.kwargs["method"], "PATCH")

    def test_notion_briefing_requires_readback(self):
        with patch.dict(os.environ, {"NOTION_TOKEN": "offline-placeholder"}, clear=True), \
             patch.object(guard, "require_autonomy"), patch("urllib.request.urlopen") as net:
            # Capture the real generated payload and simulate the saved paragraphs.
            def transport(request, **kwargs):
                if request.get_method() == "PATCH":
                    self.payload = json.loads(request.data)["children"][0]["toggle"]["children"]
                    return http_response({"results": [{"id": "saved-block"}]})
                return http_response({"results": self.payload, "has_more": False})
            net.side_effect = transport
            self.assertEqual(cloud._post_to_notion_page("page", "task", "answer", {}),
                             "notion: verified 200")
            self.assertEqual(net.call_count, 2)

    def test_notion_mismatched_readback_is_not_success(self):
        with patch.dict(os.environ, {"NOTION_TOKEN": "offline-placeholder"}, clear=True), \
             patch.object(guard, "require_autonomy"), patch("urllib.request.urlopen", side_effect=[
                 http_response({"results": [{"id": "saved-block"}]}),
                 http_response({"results": [], "has_more": False}),
             ]):
            delivery = cloud._post_to_notion_page("page", "task", "answer", {})
            self.assertEqual(delivery, "notion: content_mismatch")
            self.assertEqual(cloud._exit_code("succeeded", delivery), 3)

    def test_low_pipeline_success_is_not_only_a_router_unit_test(self):
        manager, complete = completion_manager([response("Slutsats Möjligheter Risker Rekommendation Nästa steg")])
        with patch.dict(os.environ, {"COMET_API_KEY": "offline-placeholder",
                                    "JARVIS_MONTH_SPEND_PCT": "0", "JARVIS_NOTIFY": "0"}, clear=True), \
             patch.object(guard, "require_autonomy"), \
             patch.object(supervisor, "_approval"), \
             patch.object(supervisor, "AsyncOpenAI", return_value=manager):
            result = asyncio.run(supervisor.Supervisor().chat([HumanMessage(content="Hej Jarvis")]))
            self.assertEqual(result["frugality"]["execution_status"], "succeeded")
            self.assertEqual(result["frugality"]["tier"], "LOW")
            self.assertEqual(complete.await_count, 1)


if __name__ == "__main__":
    unittest.main()
