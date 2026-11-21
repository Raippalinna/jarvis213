"""Offline, key-free safety regression tests for the multiagent orchestrator."""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from jarvis.core.agent_orchestrator import AGENTS, AgentOrchestrator, OrchestrationError
from jarvis.core.mission_engine import ExecutionEvidence, MissionError


def make(**kwargs):
    return AgentOrchestrator("Improve the main Jarvis system", **kwargs)


def fake_exec(task):
    return ExecutionEvidence("fixture:" + task.step_id, "Synthetic test artifact")


def fake_verify(evidence):
    return "fixture-readback:" + evidence.artifact_ref if evidence.artifact_ref.startswith("fixture:") else None


def run(orchestrator, step, caps=(), approvals=()):
    task = orchestrator.tasks[step]
    return orchestrator.run_one(
        step,
        adapter_role=task.role,
        execute=fake_exec,
        verify=fake_verify,
        autonomy_check=lambda _mission_id: True,
        capability_check=lambda _mission_id, _step_id, capability: capability in caps,
        approval_check=lambda _mission_id, _step_id, approval_id: approval_id in approvals,
        spend_check=lambda _mission_id, _step_id, amount: True,
    )


def test_eight_agent_stages_planned_but_execution_disabled():
    orchestrator = make()
    snapshot = orchestrator.snapshot()
    assert len(snapshot["agents"]) == 8
    assert snapshot["status"] == "planned"
    assert snapshot["execution_enabled"] is False
    assert snapshot["production_verified"] is False
    assert snapshot["steps"]["release"]["verified"] is False
    assert orchestrator.engine.ready() == ("intake",)


def test_default_cannot_execute_even_with_fake_adapter_and_permissions():
    orchestrator = make(budget_sek="200")
    with pytest.raises(OrchestrationError, match="execution_disabled"):
        run(orchestrator, "intake", caps=("deploy",), approvals=(orchestrator.approval_id("release"),))
    assert orchestrator.snapshot()["reserved_sek"] == "0"
    assert orchestrator.snapshot()["steps"]["intake"]["attempts"] == 0


def test_optional_roles_are_opt_in_and_review_depends_on_creative():
    orchestrator = make(creative=True, notifications=True)
    assert len(orchestrator.tasks) == 10
    assert orchestrator.tasks["review"].depends_on == ("testing", "creative")
    assert orchestrator.tasks["creative"].depends_on == ("architecture",)
    assert orchestrator.tasks["notification"].depends_on == ("review",)
    assert orchestrator.snapshot()["agents"]["creative"]["requires_approval"] is True
    assert orchestrator.snapshot()["agents"]["notification"]["requires_approval"] is True


@pytest.mark.parametrize("goal", ["", "no", "\x00bad", "x" * 4001])
def test_bad_goal_rejected(goal):
    with pytest.raises(OrchestrationError, match="invalid_goal"):
        AgentOrchestrator(goal)


@pytest.mark.parametrize("budget", ["-1", "NaN", "Infinity", "201", "n/a"])
def test_invalid_budget_rejected(budget):
    with pytest.raises(OrchestrationError, match="invalid_budget"):
        make(budget_sek=budget)


def test_optional_flags_must_be_real_booleans():
    with pytest.raises(OrchestrationError, match="invalid_options"):
        make(creative="yes")
    with pytest.raises(OrchestrationError, match="invalid_execution_mode"):
        make(execution_enabled="true")


def test_agent_roster_has_distinct_roles_and_risk_labels():
    assert len(AGENTS) == 10
    assert all(key == spec.role for key, spec in AGENTS.items())
    assert AGENTS["researcher"].risk == "external_read"
    assert AGENTS["release_manager"].risk == "external_publish"
    assert AGENTS["coder"].approval_required


def test_dependency_then_capability_then_approval_are_independent_gates():
    orch = make(execution_enabled=True, budget_sek="0.30")
    with pytest.raises(MissionError, match="dependency_unverified"):
        run(orch, "research", caps=("reviewed_research_query",), approvals=(orch.approval_id("research"),))
    assert run(orch, "intake")
    with pytest.raises(OrchestrationError, match="trusted_capability_required"):
        run(orch, "research")
    with pytest.raises(OrchestrationError, match="trusted_approval_required"):
        run(orch, "research", caps=("reviewed_research_query",))
    assert run(orch, "research", caps=("reviewed_research_query",), approvals=(orch.approval_id("research"),))
    assert orch.engine.records["research"].attempts == 1


def test_verifier_rejection_fails_closed():
    orch = make(execution_enabled=True)
    assert orch.run_one(
        "intake", adapter_role="strategist", execute=fake_exec, verify=lambda evidence: None,
        autonomy_check=lambda _: True,
    ) is False
    assert orch.snapshot()["status"] == "failed"
    assert orch.snapshot()["steps"]["intake"]["verified"] is False
    assert orch.engine.gate("research", capabilities=("reviewed_research_query",)) == "dependency_failed"


def test_adapter_exception_masked_and_not_reported():
    orch = make(execution_enabled=True)
    def bad_executor(_):
        raise RuntimeError("SUPER_SECRET_TOKEN=never_echo_this")
    assert orch.run_one("intake", adapter_role="strategist", execute=bad_executor, verify=fake_verify, autonomy_check=lambda _: True) is False
    assert "SUPER_SECRET_TOKEN" not in repr(orch.snapshot())
    assert orch.snapshot()["steps"]["intake"]["failure_reason"] == "execution_failed"


def test_wrong_agent_cannot_assume_other_role():
    orch = make(execution_enabled=True)
    with pytest.raises(OrchestrationError, match="agent_role_mismatch"):
        orch.run_one("intake", adapter_role="release_manager", execute=fake_exec, verify=fake_verify)


def test_unknown_step_rejected_before_execution():
    orch = make(execution_enabled=True)
    with pytest.raises(OrchestrationError, match="unknown_step"):
        orch.run_one("missing", adapter_role="strategist", execute=fake_exec, verify=fake_verify)


def test_budget_reservation_prevents_external_call():
    orch = make(execution_enabled=True, budget_sek="0")
    assert run(orch, "intake")
    with pytest.raises(OrchestrationError, match="budget_exceeded"):
        run(orch, "research", caps=("reviewed_research_query",), approvals=(orch.approval_id("research"),))
    assert orch.snapshot()["steps"]["research"]["attempts"] == 0


def test_complete_synthetic_pipeline_only_verifies_fixture_results():
    orch = make(execution_enabled=True, budget_sek="0.30")
    for step in orch.engine.order:
        task = orch.tasks[step]
        capability = AGENTS[task.role].capability
        approvals = (orch.approval_id(step),) if AGENTS[task.role].approval_required else ()
        assert run(orch, step, caps=(capability,) if capability else (), approvals=approvals)
    summary = orch.snapshot()
    assert summary["status"] == "verified"
    assert summary["production_verified"] is False
    assert summary["reserved_sek"] == "0.30"
    assert all(s["verified"] for s in summary["steps"].values())


def test_release_cannot_run_without_approval_even_after_other_steps():
    orch = make(execution_enabled=True, budget_sek="0.30")
    for step in orch.engine.order[:-1]:
        task = orch.tasks[step]
        cap = AGENTS[task.role].capability
        approval = (orch.approval_id(step),) if AGENTS[task.role].approval_required else ()
        assert run(orch, step, caps=(cap,) if cap else (), approvals=approval)
    with pytest.raises(OrchestrationError, match="trusted_approval_required"):
        run(orch, "release", caps=("deploy",))
    assert orch.snapshot()["steps"]["release"]["attempts"] == 0


def test_retry_requires_operator_and_is_bounded():
    orch = make(execution_enabled=True)
    assert not orch.run_one("intake", adapter_role="strategist", execute=lambda _: (_ for _ in ()).throw(ValueError("failure")), verify=fake_verify, autonomy_check=lambda _: True)
    with pytest.raises(OrchestrationError, match="manual_retry_approval_required"):
        orch.retry("intake")
    orch.retry("intake", operator_approved=True)
    assert not orch.run_one("intake", adapter_role="strategist", execute=lambda _: (_ for _ in ()).throw(ValueError("again")), verify=fake_verify, autonomy_check=lambda _: True)
    with pytest.raises(OrchestrationError, match="retry_limit_reached"):
        orch.retry("intake", operator_approved=True)


def test_cancel_blocks_future_steps():
    orch = make(execution_enabled=True, budget_sek="0.30")
    orch.cancel()
    with pytest.raises(MissionError, match="mission_cancelled"):
        run(orch, "intake")


def test_snapshot_does_not_leak_user_goal_or_evidence():
    goal = "SECRET_INTERNAL_PROJECT_2b27 sensitive documents"
    orch = AgentOrchestrator(goal, execution_enabled=True)
    assert run(orch, "intake")
    text = repr(orch.snapshot())
    assert goal not in text
    assert "SECRET_INTERNAL_PROJECT_2b27" not in text
    assert "fixture:intake" not in text


def test_mission_ids_are_opaque_and_unlinkable_even_for_same_goal():
    a = AgentOrchestrator("Improve   JARVIS   orchestration")
    b = AgentOrchestrator("Improve JARVIS orchestration")
    assert a.mission_id != b.mission_id
    assert len(a.mission_id) == 24
    assert all(c in "0123456789abcdef" for c in a.mission_id)


def test_missing_autonomy_readback_blocks_even_local_step():
    orch = make(execution_enabled=True)
    with pytest.raises(OrchestrationError, match="trusted_autonomy_check_required"):
        orch.run_one("intake", adapter_role="strategist", execute=fake_exec, verify=fake_verify)
    assert orch.engine.records["intake"].attempts == 0


def test_autonomy_exception_fails_closed_without_credential_leak():
    orch = make(execution_enabled=True)
    def invalid_gate(_):
        raise RuntimeError("SECRET_SUPABASE_KEY=not_for_logs")
    with pytest.raises(OrchestrationError, match="trusted_autonomy_check_required"):
        orch.run_one("intake", adapter_role="strategist", execute=fake_exec, verify=fake_verify, autonomy_check=invalid_gate)
    assert "SECRET_SUPABASE_KEY" not in repr(orch.snapshot())


def test_approval_string_alone_does_not_authorize_action():
    orch = make(execution_enabled=True, budget_sek="0.30")
    assert run(orch, "intake")
    with pytest.raises(OrchestrationError, match="trusted_approval_required"):
        orch.run_one(
            "research", adapter_role="researcher", execute=fake_exec, verify=fake_verify,
            autonomy_check=lambda _: True,
            capability_check=lambda *_: True,
            # No authenticated approval checker: matching IDs cannot be smuggled in.
        )
    assert orch.snapshot()["steps"]["research"]["attempts"] == 0


def test_provider_spend_gate_required_even_with_sufficient_local_budget():
    orch = make(execution_enabled=True, budget_sek="0.30")
    assert run(orch, "intake")
    with pytest.raises(OrchestrationError, match="trusted_spend_limit_required"):
        orch.run_one(
            "research", adapter_role="researcher", execute=fake_exec, verify=fake_verify,
            autonomy_check=lambda _: True,
            capability_check=lambda *_: True,
            approval_check=lambda *_: True,
        )
    assert orch.snapshot()["reserved_sek"] == "0"


def test_no_duplicate_step_execution_after_verification():
    orch = make(execution_enabled=True)
    assert run(orch, "intake")
    with pytest.raises(MissionError, match="step_verified"):
        run(orch, "intake")
