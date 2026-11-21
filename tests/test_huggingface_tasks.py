"""Synthetic offline tests. Prices, model, provider and quality are NOT real data."""
import asyncio
import importlib
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import yaml
import httpx
from langchain_core.messages import HumanMessage

from jarvis.agents.frugality import FrugalityAgent
from jarvis.routing import huggingface as hf
from jarvis.routing.providers import ProviderCatalog
from jarvis.routing.tiers import NoEligibleRoute, Sensitivity, Tier, TierRouter
from jarvis.safety import guard
from jarvis.safety.secrets import contains_secret, redact
from scripts.huggingface_catalog import MAX_BYTES, NoRedirect, URL, fetch_catalog
from scripts.huggingface_readiness import report
from scripts.resolve_inputs import resolve
from test_reliability import response, state

supervisor = importlib.import_module("jarvis.core.supervisor")
cloud = importlib.import_module("jarvis_cloud")
ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def fixture(policy_updates=None, snapshot_update=None, env_updates=None):
    with tempfile.TemporaryDirectory() as directory:
        now = datetime.now(timezone.utc).isoformat()
        policy = {
            "schema_version": 1, "enabled": True, "approval_reference": "SYNTHETIC TEST ONLY",
            "model_id": "test-org/text", "provider_id": "unit-provider", "tier": "LOW",
            "data_policy_approved": True, "quality_index": 0.9,
            "quality_evidence": "SYNTHETIC TEST ONLY", "usd_sek_assumption": 10,
            "max_input_tokens": 8192, "max_output_tokens": 600,
            "max_estimated_cost_sek": 0.25,
        }
        policy.update(policy_updates or {})
        snapshot = {
            "source_url": hf.HF_MODELS_URL, "fetched_at": now,
            "pricing_unit": "usd_per_1m_tokens",
            "data": [{
                "id": "test-org/text",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "providers": [{
                    "provider": "unit-provider", "status": "live", "context_length": 32768,
                    "pricing": {"input": 1, "output": 2},
                }],
            }],
        }
        if snapshot_update:
            snapshot_update(snapshot)
        policy_path, catalog_path = Path(directory) / "policy.json", Path(directory) / "catalog.json"
        policy_path.write_text(json.dumps(policy))
        catalog_path.write_text(json.dumps(snapshot))
        env = {
            "JARVIS_PROVIDER": "huggingface", "JARVIS_ENABLE_HUGGINGFACE": "1",
            "HF_TOKEN": "offline-placeholder", "JARVIS_TIER": "LOW",
            "JARVIS_HF_POLICY_PATH": str(policy_path), "JARVIS_HF_CATALOG_PATH": str(catalog_path),
            "JARVIS_MONTH_SPEND_PCT": "10", "JARVIS_HF_BUDGET_CHECKED_AT": now,
        }
        env.update(env_updates or {})
        with patch.dict(os.environ, env, clear=True):
            yield ProviderCatalog()


def initial():
    current = state()
    current["messages"] = [HumanMessage(content="Sammanfatta texten: Ett tydligt mål hjälper teamet.")]
    current["frugality"] = {}
    return current


class HFConfigurationTests(unittest.TestCase):
    def test_shipped_configuration_is_incomplete_and_off(self):
        policy = json.loads((ROOT / "config/huggingface.json").read_text())
        self.assertIs(policy["enabled"], False)
        self.assertIs(policy["data_policy_approved"], False)
        for key in ("model_id", "provider_id", "approval_reference", "quality_evidence"):
            self.assertEqual(policy[key], "")
        for key in ("quality_index", "usd_sek_assumption", "max_estimated_cost_sek"):
            self.assertIsNone(policy[key])

    def test_default_route_ignores_hf_enable_flag(self):
        with patch.dict(os.environ, {"JARVIS_ENABLE_HUGGINGFACE": "1"}, clear=True):
            catalog = ProviderCatalog()
        self.assertEqual(catalog.integration_status["huggingface"], "not_selected")
        self.assertNotIn("huggingface", catalog.providers)
        self.assertTrue(catalog.tiers["LOW"]["chain"])

    def test_selected_but_disabled_has_no_fallback(self):
        with fixture(env_updates={"JARVIS_ENABLE_HUGGINGFACE": "0"}) as catalog:
            self.assertEqual(catalog.integration_status["huggingface"], "disabled")
            self.assertTrue(all(not item["chain"] for item in catalog.tiers.values()))
            with self.assertRaises(NoEligibleRoute):
                TierRouter(catalog).choose(Tier.LOW, month_spend_pct=10)

    def test_valid_configuration_pins_one_provider_and_converts_units(self):
        with fixture() as catalog:
            provider = catalog.get("huggingface")
            self.assertEqual(provider.models[0].id, "test-org/text:unit-provider")
            self.assertEqual(provider.base_url, hf.HF_BASE_URL)
            self.assertAlmostEqual(provider.cost_per_1k_input_sek, 0.01)
            self.assertAlmostEqual(provider.cost_per_1k_output_sek, 0.02)
            self.assertEqual(len(catalog.tiers["LOW"]["chain"]), 1)
            self.assertFalse(catalog.tiers["MED"]["chain"])

    def test_invalid_policy_fails_closed(self):
        cases = [
            {"enabled": False}, {"data_policy_approved": False}, {"approval_reference": ""},
            {"quality_index": None}, {"quality_index": 0.1}, {"quality_index": float("nan")},
            {"quality_evidence": ""}, {"model_id": "test-org/text:fastest"},
            {"provider_id": "auto"}, {"provider_id": "fastest"}, {"provider_id": "cheapest"},
            {"provider_id": "preferred"}, {"tier": "FREE"}, {"usd_sek_assumption": 0},
            {"max_estimated_cost_sek": 2}, {"max_output_tokens": 2001},
            {"max_output_tokens": True}, {"max_input_tokens": 0}, {"quality_index": True},
        ]
        for update in cases:
            with self.subTest(update=update), fixture(policy_updates=update) as catalog:
                self.assertEqual(catalog.integration_status["huggingface"], "configuration_blocked")
                with self.assertRaises(NoEligibleRoute):
                    hf.require_profile(catalog)

    def test_bad_catalog_never_uses_another_route(self):
        def provider_change(key, value):
            return lambda snapshot: snapshot["data"][0]["providers"][0].update({key: value})
        cases = [
            lambda s: s.update(source_url="https://unit.invalid/models"),
            lambda s: s.update(pricing_unit="usd_per_token"),
            lambda s: s.update(fetched_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat()),
            lambda s: s.update(fetched_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()),
            lambda s: s.update(data=[]),
            lambda s: s["data"].append(s["data"][0].copy()),
            provider_change("status", "error"), provider_change("context_length", 100),
            provider_change("pricing", {}), provider_change("pricing", {"input": -1, "output": 2}),
        ]
        for update in cases:
            with self.subTest(update=update), fixture(snapshot_update=update) as catalog:
                self.assertEqual(catalog.integration_status["huggingface"], "configuration_blocked")
                self.assertTrue(all(not item["chain"] for item in catalog.tiers.values()))

    def test_missing_token_is_not_inference_readiness(self):
        with fixture(env_updates={"HF_TOKEN": ""}) as catalog:
            self.assertEqual(catalog.integration_status["huggingface"], "credential_missing")
            self.assertFalse(report()["configuration_ready"])

    def test_budget_missing_stale_future_and_nonfinite_block(self):
        cases = [
            {"JARVIS_MONTH_SPEND_PCT": ""}, {"JARVIS_MONTH_SPEND_PCT": "nan"},
            {"JARVIS_MONTH_SPEND_PCT": "-1"}, {"JARVIS_HF_BUDGET_CHECKED_AT": ""},
            {"JARVIS_HF_BUDGET_CHECKED_AT": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()},
            {"JARVIS_HF_BUDGET_CHECKED_AT": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        ]
        for update in cases:
            with self.subTest(update=update), fixture(env_updates=update) as catalog:
                with self.assertRaises(NoEligibleRoute) as context:
                    hf.require_budget(catalog)
                self.assertEqual(context.exception.status, "budget_unavailable")

    def test_budget_veto_cannot_switch_to_another_provider(self):
        with fixture(env_updates={"JARVIS_MONTH_SPEND_PCT": "99"}) as catalog:
            with self.assertRaises(NoEligibleRoute) as context:
                hf.require_budget(catalog)
            self.assertEqual(context.exception.status, "budget_blocked")

    def test_tier_mismatch_blocks(self):
        with fixture() as catalog:
            with self.assertRaises(NoEligibleRoute):
                catalog.huggingface_profile.check(catalog, "MED", [{"content": "Hej"}])

    def test_token_and_estimated_cost_ceilings_block(self):
        for policy in ({"max_input_tokens": 100}, {"max_estimated_cost_sek": 0.00001}):
            with self.subTest(policy=policy), fixture(policy_updates=policy) as catalog:
                with self.assertRaises(NoEligibleRoute):
                    catalog.huggingface_profile.check(catalog, "LOW", [{"content": "Hej"}])

    def test_confidential_data_cannot_escalate_out_of_hf(self):
        with fixture() as catalog:
            with self.assertRaises(NoEligibleRoute):
                TierRouter(catalog).choose(Tier.LOW, sensitivity=Sensitivity.CONFIDENTIAL,
                                          month_spend_pct=10)

    def test_hf_tokens_are_detected_and_redacted(self):
        token = "hf_" + "SYNTHETICONLY" * 3
        self.assertTrue(contains_secret(token))
        self.assertNotIn(token, redact(token))

    def test_readiness_does_not_use_network(self):
        with fixture(), patch("urllib.request.urlopen") as network:
            value = report()
            self.assertEqual(value["status"], "configured_for_review")
            self.assertEqual(value["completion_requests"], 0)
            self.assertIs(value["inference_tested"], False)
            network.assert_not_called()

    def test_dry_run_stops_hf_graph_without_any_lookup(self):
        with fixture(env_updates={"JARVIS_DRY_RUN": "1"}) as catalog, \
             patch.object(supervisor, "_catalog", catalog), \
             patch("urllib.request.urlopen") as network, \
             patch.object(supervisor, "AsyncOpenAI") as provider:
            result = asyncio.run(supervisor.Supervisor().chat([HumanMessage(content="Hej")]))
        self.assertEqual(result["frugality"]["execution_status"], "paused")
        network.assert_not_called()
        provider.assert_not_called()


class HFRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(guard, "require_autonomy").start()
        self.addCleanup(patch.stopall)

    def run_completion(self, catalog, completions, current=None):
        create = AsyncMock(side_effect=completions)
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
        manager.__aexit__ = AsyncMock(return_value=False)
        with patch.object(supervisor, "_catalog", catalog), \
             patch.object(supervisor, "_frugality", FrugalityAgent(catalog)), \
             patch.object(supervisor, "AsyncOpenAI", return_value=manager) as factory:
            current = asyncio.run(supervisor.frugality_preflight(current or initial()))
            current = asyncio.run(supervisor.execute(current))
        return current, create, factory

    def test_success_is_one_pinned_request_with_no_retry_or_redirect(self):
        with fixture() as catalog:
            current, create, factory = self.run_completion(catalog, [response("Ett kort svar.")])
        self.assertEqual(current["frugality"]["execution_status"], "succeeded")
        self.assertEqual(create.await_count, 1)
        self.assertEqual(create.call_args.kwargs["model"], "test-org/text:unit-provider")
        self.assertEqual(create.call_args.kwargs["max_tokens"], 600)
        self.assertIs(create.call_args.kwargs["stream"], False)
        self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
        self.assertFalse(factory.call_args.kwargs["http_client"].follow_redirects)
        asyncio.run(factory.call_args.kwargs["http_client"].aclose())

    def test_empty_truncated_filtered_and_timeout_never_fallback(self):
        for answer in [response(""), response("kort", "length"),
                       response("filter", "content_filter"), TimeoutError("PRIVATE_ERROR")]:
            with self.subTest(answer=type(answer).__name__), fixture() as catalog:
                current, create, factory = self.run_completion(catalog, [answer, response("NO")])
                self.assertEqual(create.await_count, 1)
                self.assertEqual(current["frugality"]["execution_status"], "failed")
                self.assertNotIn("PRIVATE_ERROR", str(current))
                self.assertGreater(current["frugality"]["reserved_cost_sek"], 0)
                if isinstance(answer, TimeoutError):
                    self.assertTrue(current["frugality"]["unreconciled_cost"])
                asyncio.run(factory.call_args.kwargs["http_client"].aclose())

    def test_missing_and_malformed_usage_are_unknown_not_free(self):
        for usage in (None, SimpleNamespace(prompt_tokens=-1, completion_tokens=None)):
            answer = response("Svar")
            answer.usage = usage
            with self.subTest(usage=usage), fixture() as catalog:
                current, _, factory = self.run_completion(catalog, [answer])
                self.assertTrue(current["frugality"]["unreconciled_cost"])
                self.assertTrue(current["frugality"]["cost_is_estimate"])
                self.assertGreater(current["frugality"]["actual_cost_sek"], 0)
                asyncio.run(factory.call_args.kwargs["http_client"].aclose())

    def test_secret_input_never_calls_model(self):
        current = initial()
        current["messages"] = [HumanMessage(content="hf_" + "SYNTHETICONLY" * 3)]
        with fixture() as catalog:
            current, create, factory = self.run_completion(catalog, [], current)
        self.assertEqual(current["frugality"]["execution_status"], "data_blocked")
        create.assert_not_called()
        factory.assert_not_called()

    def test_secret_output_is_not_used_as_answer(self):
        token = "hf_" + "SYNTHETICONLY" * 3
        with fixture() as catalog:
            current, _, factory = self.run_completion(catalog, [response(token)])
        self.assertEqual(current["frugality"]["execution_status"], "failed")
        self.assertNotIn(token, str(current))
        asyncio.run(factory.call_args.kwargs["http_client"].aclose())

    def test_stop_before_call_never_requests_inference(self):
        self.guard.side_effect = guard.SafetyStop("model_call", "disabled")
        with fixture() as catalog:
            current, create, factory = self.run_completion(catalog, [])
        self.assertEqual(current["frugality"]["execution_status"], "paused")
        create.assert_not_called()
        factory.assert_not_called()

    def test_disabled_profile_stops_graph_before_memory_approval_or_provider(self):
        with fixture(env_updates={"JARVIS_ENABLE_HUGGINGFACE": "0"}) as catalog, \
             patch.object(supervisor, "_catalog", catalog), \
             patch.object(supervisor, "_approval") as approvals, \
             patch.object(supervisor, "build_context") as memory, \
             patch.object(supervisor, "AsyncOpenAI") as provider:
            result = asyncio.run(supervisor.Supervisor().chat([HumanMessage(content="Hej")]))
            self.assertEqual(cloud._execution_status(result), "route_blocked")
            for mock in (approvals, memory, provider):
                mock.assert_not_called()

    def test_hf_has_no_memory_approval_writes_or_notifications(self):
        with fixture(), patch.object(supervisor, "build_context") as memory, \
             patch.object(supervisor, "_memory_store") as store, \
             patch.object(supervisor, "_approval") as approvals, \
             patch.object(supervisor, "notify_all") as notify:
            current = asyncio.run(supervisor.approval_gate(initial()))
            current = asyncio.run(supervisor.load_memory(current))
            current["frugality"] = {"execution_status": "succeeded"}
            current = asyncio.run(supervisor.reflect(current))
            self.assertEqual(current["frugality"]["memory_status"], "disabled_hf_text_profile")
            for mock in (memory, store, approvals, notify):
                self.assertFalse(mock.mock_calls)

    def test_external_action_request_is_blocked_not_saved_as_approval(self):
        current = initial()
        current["messages"] = [HumanMessage(content="Skicka mejl till kunden")]
        with fixture(), patch.object(supervisor, "_approval") as approvals:
            result = asyncio.run(supervisor.approval_gate(current))
            self.assertEqual(result["frugality"]["execution_status"], "route_blocked")
            self.assertEqual(supervisor._approval_route(result), "blocked")
            self.assertFalse(approvals.mock_calls)

    def test_injected_memory_or_model_change_is_blocked(self):
        with fixture() as catalog, patch.object(supervisor, "_catalog", catalog), \
             patch.object(supervisor, "_frugality", FrugalityAgent(catalog)), \
             patch.object(supervisor, "AsyncOpenAI") as provider:
            current = asyncio.run(supervisor.frugality_preflight(initial()))
            current["memory_context"]["text"] = "private context"
            result = asyncio.run(supervisor.execute(current))
            self.assertEqual(result["frugality"]["execution_status"], "route_blocked")
            provider.assert_not_called()

    def test_expired_budget_between_preflight_and_execution_blocks(self):
        with fixture() as catalog, patch.object(supervisor, "_catalog", catalog), \
             patch.object(supervisor, "_frugality", FrugalityAgent(catalog)), \
             patch.object(supervisor, "AsyncOpenAI") as provider:
            current = asyncio.run(supervisor.frugality_preflight(initial()))
            os.environ["JARVIS_HF_BUDGET_CHECKED_AT"] = ""
            result = asyncio.run(supervisor.execute(current))
            self.assertEqual(result["frugality"]["execution_status"], "budget_unavailable")
            provider.assert_not_called()


class HFPublicCatalogTests(unittest.TestCase):
    def test_exact_public_get_without_authorization(self):
        opener = MagicMock()
        reply = opener.open.return_value.__enter__.return_value
        reply.status = 200
        reply.read.return_value = json.dumps({"data": [{"id": "test-org/text"}]}).encode()
        snapshot = fetch_catalog(opener)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, URL)
        self.assertEqual(request.get_method(), "GET")
        self.assertFalse(request.has_header("Authorization"))
        self.assertEqual(snapshot["pricing_unit"], "usd_per_1m_tokens")

    def test_empty_malformed_and_oversized_catalogs_fail(self):
        for raw in (b"{}", b'{"data":[]}', b"not-json", b"x" * (MAX_BYTES + 1)):
            with self.subTest(size=len(raw)):
                opener = MagicMock()
                reply = opener.open.return_value.__enter__.return_value
                reply.status, reply.read.return_value = 200, raw
                with self.assertRaises(ValueError):
                    fetch_catalog(opener)

    def test_redirect_is_rejected(self):
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://unit.invalid")


class HFTransportTests(unittest.TestCase):
    def test_full_graph_with_real_sdk_and_mock_transport_only(self):
        for status in (200, 302, 500):
            requests = []

            def handle(request):
                requests.append(request)
                self.assertEqual(str(request.url), hf.HF_BASE_URL + "/chat/completions")
                if status == 302:
                    return httpx.Response(302, headers={"Location": "https://unit.invalid"})
                if status == 500:
                    return httpx.Response(500, json={"error": {"message": "SYNTHETIC ERROR"}})
                return httpx.Response(200, json={
                    "id": "offline", "object": "chat.completion", "created": 0,
                    "model": "test-org/text",
                    "choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": "Ett kort textutkast."}}],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
                })

            with self.subTest(status=status), fixture() as catalog:
                client = httpx.AsyncClient(transport=httpx.MockTransport(handle),
                                           follow_redirects=False)
                with patch.object(supervisor, "_catalog", catalog), \
                     patch.object(supervisor, "_frugality", FrugalityAgent(catalog)), \
                     patch.object(guard, "require_autonomy"), \
                     patch.object(hf, "make_http_client", return_value=client), \
                     patch.object(supervisor, "_approval") as approvals, \
                     patch.object(supervisor, "build_context") as memory, \
                     patch.object(supervisor, "_memory_store") as store, \
                     patch.object(supervisor, "notify_all") as notify:
                    result = asyncio.run(supervisor.Supervisor().chat(
                        [HumanMessage(content="Sammanfatta texten: Vi arbetar tillsammans.")]))
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0].method, "POST")
                sent = json.loads(requests[0].content)
                self.assertEqual(sent["model"], "test-org/text:unit-provider")
                self.assertEqual(sent["max_tokens"], 600)
                self.assertIs(sent["stream"], False)
                self.assertNotIn("tools", sent)
                self.assertNotIn("X-HF-Bill-To", requests[0].headers)
                self.assertEqual(result["frugality"]["execution_status"],
                                 "succeeded" if status == 200 else "failed")
                for mock in (approvals, memory, store, notify):
                    self.assertFalse(mock.mock_calls)
                self.assertTrue(client.is_closed)


class HFWorkflowTests(unittest.TestCase):
    def test_default_inputs_do_not_enable_hf(self):
        self.assertEqual(resolve("workflow_dispatch", {}, {"task": "Hej"})["provider"], "default")

    def test_hf_is_manual_text_only_not_free_or_notional_delivery(self):
        for event_name, extras in [
            ("repository_dispatch", {}), ("workflow_call", {}),
            ("workflow_dispatch", {"tier": "FREE"}),
            ("workflow_dispatch", {"notion_page_id": "private-page"}),
            ("workflow_dispatch", {"task": "x" * 6001}),
        ]:
            with self.subTest(event=event_name, extras=extras), self.assertRaises(ValueError):
                values = {"task": "Sammanfatta", "provider": "huggingface", **extras}
                resolve(event_name, {"client_payload": values}, values)

    def test_unknown_provider_never_turns_into_default(self):
        with self.assertRaises(ValueError):
            resolve("workflow_dispatch", {}, {"task": "Hej", "provider": "arbitrary"})

    def test_workflow_keeps_explicit_selection_and_default_off(self):
        workflow = yaml.load((ROOT / ".github/workflows/jarvis-cloud.yml").read_text(),
                             Loader=yaml.BaseLoader)
        inputs = workflow["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["provider"]["default"], "default")
        steps = workflow["jobs"]["execute"]["steps"]
        run = next(step for step in steps if step.get("name") == "Run JARVIS")
        self.assertIn("|| '0'", run["env"]["JARVIS_ENABLE_HUGGINGFACE"])
        self.assertIn("steps.inp.outputs.provider == 'huggingface'", run["env"]["HF_TOKEN"])
        self.assertIn("vars.JARVIS_ENABLE_HUGGINGFACE == '1'", run["env"]["HF_TOKEN"])
        catalog = next(step for step in steps if "huggingface_catalog.py" in step.get("run", ""))
        self.assertNotIn("env", catalog)


if __name__ == "__main__":
    unittest.main()
