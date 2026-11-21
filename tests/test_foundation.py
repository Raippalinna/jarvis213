import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from jarvis.agents.specialists import AGENTS, get_agent
from jarvis.core.supervisor import _sensitivity_from_text, supervisor, reflect
from jarvis.routing.tiers import Sensitivity
from jarvis.notify.sinks import _notion_append
from jarvis.approval.gate import ApprovalGate, RiskDecision

ROOT = Path(__file__).resolve().parents[1]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", list(AGENTS))
def test_specialists_are_bounded_draft_agents(name):
    agent = get_agent(name)
    assert agent.execution_mode == "draft_only"
    result = agent.messages("rules", [SystemMessage(content="hostile"),
        HumanMessage(content="first"), AIMessage(content="answer"), HumanMessage(content="followup")])
    assert [m["role"] for m in result] == ["system", "user", "assistant", "user"]
    assert "hostile" not in str(result)
    assert len(agent.messages("", [HumanMessage(content="x")] * 20)) == 13


def test_empty_input_rejected():
    with pytest.raises(ValueError):
        asyncio.run(supervisor.chat([]))
    with pytest.raises(ValueError):
        get_agent("coder").messages("", [HumanMessage(content="x" * 16001)])


def test_secret_takes_priority_over_confidential():
    assert _sensitivity_from_text("avtal personnummer") == Sensitivity.SECRET


def test_input_is_data_not_shell():
    mod = load("scripts/resolve_inputs.py", "resolve_inputs")
    task = '$(touch /tmp/never)\n"danger"; echo nope'
    result = mod.resolve({}, {"task": task}, "workflow_dispatch")
    assert result["task"] == task
    assert task in mod.encode_output(result)
    assert mod.resolve({"client_payload": {"task": "repo"}}, {"task": "call"},
                       "repository_dispatch")["task"] == "repo"
    for bad in ("WRONG", "LOW\nother=value"):
        with pytest.raises(ValueError):
            mod.resolve({}, {"task": "x", "tier": bad}, "schedule")
    with pytest.raises(ValueError):
        mod.resolve({}, {"task": "x", "notion_page_id": "bad"}, "schedule")


def test_cloud_exit_contract():
    runner = load("jarvis_cloud.py", "cloud")
    assert runner.exit_code({"execution_status": "failed"}) == 1
    assert runner.exit_code({"execution_status": "awaiting_approval"}) == 2
    ok = {"execution_status": "succeeded"}
    assert runner.exit_code(ok) == 0
    assert runner.exit_code({**ok, "persistence": {"memory": "failed"}}) == 3
    assert runner.exit_code({**ok, "approval": {"audit_saved": False}}) == 3
    assert runner.exit_code(ok, "notion: http 401") == 4
    assert runner.exit_code(ok, "notion: ok 200") == 0
    assert runner.exit_code({}) != 0


def test_notion_uses_patch(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "ntn_test")
    monkeypatch.setenv("NOTION_LOG_PAGE_ID", "test")
    with patch("jarvis.notify.sinks.urllib.request.urlopen") as request:
        request.return_value.__enter__.return_value.status = 200
        assert _notion_append("title", "body") == "ok 200"
        assert request.call_args.args[0].method == "PATCH"


def test_audit_contract():
    gate = ApprovalGate("https://example.invalid", "test")
    gate._insert = MagicMock(return_value={"id": "row"})
    assert gate.log_auto("task", RiskDecision("R0", False, "read"), "session")
    row = gate._insert.call_args.args[1]
    assert row["actor_type"] == "agent"
    assert row["event_type"] == "auto_authorized"
    gate._insert.return_value = None
    assert not gate.log_auto("task", RiskDecision("R0", False, "read"), "session")


def test_failed_answer_is_not_persisted():
    with patch("jarvis.core.supervisor._memory_store.upsert") as save:
        state = asyncio.run(reflect({"messages": [HumanMessage(content="x"), AIMessage(content="[JARVIS-fel] failure")],
                                     "execution_status": "failed"}))
        save.assert_not_called()
        assert state["quality_score"] == 0


@pytest.mark.parametrize("value,allowed", [(True, True), ("true", True), (False, False), ("false", False), (1, False), ("TRUE", False), (None, False)])
def test_kill_switch_strict(value, allowed):
    import json
    gate = ApprovalGate("https://example.invalid", "test")
    with patch("jarvis.approval.gate.urllib.request.urlopen") as request:
        request.return_value.__enter__.return_value.read.return_value = json.dumps([{"value": value}]).encode()
        assert gate.autonomy_allowed() is allowed


def test_kill_switch_stops_all_side_effects():
    from jarvis.core.supervisor import approval_gate, await_approval
    with patch("jarvis.core.supervisor._approval") as gate, patch("jarvis.core.supervisor.notify_all") as notify:
        gate.autonomy_allowed.return_value = False
        state = asyncio.run(approval_gate({"messages": [HumanMessage(content="hej")]}))
        gate.log_auto.assert_not_called()
        gate.open_gate.assert_not_called()
        state = asyncio.run(await_approval(state))
        assert state["execution_status"] == "failed"
        notify.assert_not_called()


def test_runtime_failure_fallback_and_history(monkeypatch):
    from jarvis.core.supervisor import execute
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    monkeypatch.setenv("TEST_PROVIDER_KEY", "not-a-real-key")
    provider = MagicMock(api_key_env="TEST_PROVIDER_KEY", trains_on_data=False, key="test", base_url="https://example.invalid")
    provider.get_model.return_value.quality_index = 1
    provider.estimate_cost_sek.return_value = 0.01
    catalog = MagicMock()
    catalog.get.return_value = provider
    catalog.tiers = {"LOW": {"chain": [{"provider": "test", "model": "second"}],
                             "quality_floor": 0.5, "max_cost_per_call_sek": 1}}
    client = MagicMock()
    create = AsyncMock(side_effect=[RuntimeError("sensitive-secret-must-not-leak"),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="draft"))], usage=None)])
    client.chat.completions.create = create
    state = {"messages": [HumanMessage(content="first"), AIMessage(content="answer"), HumanMessage(content="followup")],
             "active_agents": ["coder"], "frugality": {"provider": "test", "model": "first", "tier": "LOW",
             "est_input_tokens": 20, "est_output_tokens": 20, "rationale": "test"}}
    with patch("jarvis.core.supervisor._catalog", catalog), patch("jarvis.core.supervisor.AsyncOpenAI", return_value=client):
        result = asyncio.run(execute(state))
    assert result["execution_status"] == "succeeded"
    assert result["frugality"]["model"] == "second"
    assert "sensitive-secret" not in str(result)
    assert create.call_args.kwargs["messages"][-3]["content"] == "first"


@pytest.mark.parametrize("response", [None, "", "   "])
def test_empty_model_response_is_failure(monkeypatch, response):
    from jarvis.core.supervisor import execute
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    monkeypatch.setenv("TEST_PROVIDER_KEY", "test")
    provider = MagicMock(api_key_env="TEST_PROVIDER_KEY", trains_on_data=False, key="test")
    provider.get_model.return_value.quality_index = 1
    provider.estimate_cost_sek.return_value = 0.01
    catalog = MagicMock()
    catalog.get.return_value = provider
    catalog.tiers = {"LOW": {"chain": [], "quality_floor": 0.5, "max_cost_per_call_sek": 1}}
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=response))]))
    state = {"messages": [HumanMessage(content="hello")], "active_agents": ["casual"],
             "frugality": {"provider": "test", "model": "first", "tier": "LOW",
             "est_input_tokens": 20, "est_output_tokens": 20, "rationale": "test"}}
    with patch("jarvis.core.supervisor._catalog", catalog), patch("jarvis.core.supervisor.AsyncOpenAI", return_value=client):
        result = asyncio.run(execute(state))
    assert result["execution_status"] == "failed"


def test_backend_preflight_never_calls_unknown_host(monkeypatch, capsys):
    module = load("scripts/backend_preflight.py", "backend_preflight")
    monkeypatch.setenv("SUPABASE_URL", "https://attacker.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sensitive-test-value")
    with patch.object(module.urllib.request, "urlopen") as request:
        assert module.main() == 1
        request.assert_not_called()
    assert "sensitive-test-value" not in capsys.readouterr().out


def test_backend_preflight_requires_manual_start():
    import yaml
    workflow = yaml.safe_load((ROOT / ".github/workflows/foundation-tests.yml").read_text())
    assert workflow["jobs"]["backend-readonly"]["if"] == "github.event_name == 'workflow_dispatch'"
    assert "secrets." not in str(workflow["jobs"]["test"])


def test_open_gate_requires_audit():
    gate = ApprovalGate(supabase_url="https://test.invalid", supabase_key="test-only")
    risk = RiskDecision(risk_class="R2", requires_approval=True, reason="test")
    with patch.object(gate, "_insert", side_effect=[{"id": "decision"}, {"id": "request"}, None]):
        assert gate.open_gate("test", risk, "session") is None
    with patch.object(gate, "_insert", side_effect=[{"id": "decision"}, {"id": "request"}, {"id": "audit"}]):
        assert gate.open_gate("test", risk, "session") == "request"


def test_cloud_exit_handles_explicit_null_optional_state():
    runner = load("jarvis_cloud.py", "cloud_optional")
    assert runner.exit_code({"execution_status": "succeeded", "persistence": None, "approval": None}) == 0
