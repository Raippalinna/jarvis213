"""Opt-in LangGraph / Agent Orchestra bridge tests; no live model or network."""
from __future__ import annotations
import asyncio
from unittest.mock import Mock

from langchain_core.messages import HumanMessage
from jarvis.core import supervisor as supervisor_module
from jarvis.core.state import IntentClassification


def _state(goal="Build the main JARVIS system"):
    return {
        "messages": [HumanMessage(content=goal)],
        "intent": IntentClassification(category="coding", confidence=0.85),
        "session_id": "fixture",
        "mission_preview": None,
    }


def test_flag_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_AGENT_ORCHESTRA_PREVIEW", raising=False)
    state = _state()
    returned = asyncio.run(supervisor_module.prepare_mission_preview(state))
    assert returned["mission_preview"] is None


def test_explicit_flag_creates_read_only_dag(monkeypatch):
    monkeypatch.setenv("JARVIS_AGENT_ORCHESTRA_PREVIEW", "1")
    state = asyncio.run(supervisor_module.prepare_mission_preview(_state()))
    plan = state["mission_preview"]
    assert plan["status"] == "planned"
    assert plan["execution_enabled"] is False
    assert plan["production_verified"] is False
    assert len(plan["agents"]) == 8
    assert all(record["status"] == "pending" for record in plan["steps"].values())


def test_malformed_goal_never_activates_execution(monkeypatch):
    monkeypatch.setenv("JARVIS_AGENT_ORCHESTRA_PREVIEW", "1")
    plan = asyncio.run(supervisor_module.prepare_mission_preview(_state("x")))["mission_preview"]
    assert plan["status"] == "blocked"
    assert plan["execution_enabled"] is False


def test_flag_does_not_leak_goal_into_preview(monkeypatch):
    monkeypatch.setenv("JARVIS_AGENT_ORCHESTRA_PREVIEW", "1")
    secret_goal = "sensitive private draft ACME_928141 extremely confidential"
    snapshot = asyncio.run(supervisor_module.prepare_mission_preview(_state(secret_goal)))["mission_preview"]
    assert secret_goal not in repr(snapshot)
    assert "ACME_928141" not in repr(snapshot)


def test_approval_gate_still_runs_after_preview(monkeypatch):
    monkeypatch.setenv("JARVIS_AGENT_ORCHESTRA_PREVIEW", "1")
    state = _state("skicka mejl till kunden")  # Risk R2
    state = asyncio.run(supervisor_module.prepare_mission_preview(state))
    monkeypatch.setattr(supervisor_module._approval, "open_gate", Mock(return_value="fixture-request-id"))
    state = asyncio.run(supervisor_module.approval_gate(state))
    assert state["approval"]["halted"] is True
    assert state["approval"]["risk_class"] == "R2"
    assert state["mission_preview"]["execution_enabled"] is False


def test_graph_routing_passes_preview_then_approval():
    graph = supervisor_module.create_graph().get_graph()
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("route", "prepare_mission_preview") in edges
    assert ("prepare_mission_preview", "approval_gate") in edges
