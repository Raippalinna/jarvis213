"""Nyckelfria tester. Nätverk, externa skrivningar och LLM får inte användas."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.missions import plan_mission, assess_receipt


def _step(plan, name):
    return next(s for s in plan["steps"] if s["id"] == name)


def test_plan_has_no_side_effects_or_claimed_execution():
    p = plan_mission("Färdigställ hela Jarvis")
    assert p["status"] == "prepared" and not p["execution_allowed"]
    assert p["agents_executed"] == p["external_calls"] == p["cost_sek"] == 0
    assert all(not s["executed"] and s["evidence"] == "not_collected" for s in p["steps"])


def test_missing_connectors_are_blocked_not_assumed_available():
    p = plan_mission("Färdigställ hela Jarvis")
    assert "connector_not_e2e_verified" in _step(p, "research")["blocking_reasons"]
    assert "connector_not_e2e_verified" in _step(p, "release")["blocking_reasons"]


def test_connected_and_reviewed_read_remains_plan_only():
    p = plan_mission("Färdigställ hela Jarvis", connector_statuses={"firecrawl": "e2e_verified"}, public_query_reviewed=True)
    assert _step(p, "research")["status"] == "planned"
    assert _step(p, "implementation")["status"] == "blocked"
    assert not p["execution_allowed"]


def test_write_deploy_always_require_explicit_approval():
    p = plan_mission("Färdigställ Jarvis", connector_statuses={"github":"e2e_verified", "vercel":"e2e_verified"})
    for sid in ("implementation", "release"):
        assert "explicit_action_approval_required" in _step(p, sid)["blocking_reasons"]


def test_external_research_must_have_reviewed_public_query():
    p = plan_mission("Granska offentlig information", connector_statuses={"firecrawl":"e2e_verified"})
    assert "public_query_not_reviewed" in _step(p, "research")["blocking_reasons"]


def test_secret_goal_is_not_returned_in_output():
    raw = "Utvärdera intern kundhemlighet XYZ-SENSITIVE-EXAMPLE"
    p = plan_mission(raw, sensitivity="secret")
    assert raw not in str(p) and "XYZ-SENSITIVE" not in str(p)


def test_disallowed_execute_mode_fails_closed():
    p = plan_mission("Fixa mitt system", mode="execute")
    assert p["status"] == "blocked" and p["steps"] == []


def test_bad_policy_inputs_fail_closed():
    assert plan_mission("Fixa mitt system", connector_statuses={"github":"connected"})["status"] == "blocked"
    assert plan_mission("Fixa mitt system", sensitivity="unknown")["status"] == "blocked"
    assert plan_mission("Fixa mitt system", public_query_reviewed=1)["status"] == "blocked"


def test_cancellation_prevents_planning():
    p = plan_mission("Fixa mitt system", cancelled=True)
    assert p["status"] == "cancelled" and not p["steps"]


def test_optional_creative_requires_scope_and_cost_review():
    p = plan_mission("Gör en kreativ video med Higgsfield", connector_statuses={"higgsfield":"e2e_verified"})
    s = _step(p, "creative")
    assert "cost_or_scope_review_required" in s["blocking_reasons"]
    assert s["status"] == "blocked"


def test_optional_slack_send_requires_approval():
    p = plan_mission("Rapportera i Slack", connector_statuses={"slack":"e2e_verified"})
    assert "explicit_action_approval_required" in _step(p, "notify")["blocking_reasons"]


def test_fingerprint_is_deterministic():
    assert plan_mission("  Fixa   systemet  ")["mission_id"] == plan_mission("Fixa systemet")["mission_id"]


def test_receipt_cannot_claim_completion_even_with_full_fields():
    p = plan_mission("Fixa systemet")
    receipt = {"step_id":"testing", "mission_id":p["mission_id"], "artifact_sha256":"a"*64,
               "evidence_url":"https://github.com/example/repo/actions/runs/1", "outcome":"success",
               "observed_at":"2026-11-05T20:00:00+00:00"}
    result = assess_receipt(p, receipt, now=datetime(2026, 11, 5, 22, 0, tzinfo=timezone.utc))
    assert result["status"] == "eligible_for_external_review"
    assert result["externally_verified"] is False and result["mission_completed"] is False


def test_receipt_without_approval_is_blocked_for_writes():
    p = plan_mission("Fixa systemet")
    receipt = {"step_id":"implementation", "mission_id":p["mission_id"], "artifact_sha256":"a"*64,
               "evidence_url":"https://github.com/example/repo", "outcome":"success",
               "observed_at":"2026-11-05T20:00:00Z"}
    result = assess_receipt(p, receipt, now=datetime(2026, 11, 5, 21, 0, tzinfo=timezone.utc))
    assert "independent_approval_reference_required" in result["reasons"]


def test_receipt_rejects_future_observation_and_bad_url():
    p = plan_mission("Fixa systemet")
    receipt = {"step_id":"review", "mission_id":p["mission_id"], "artifact_sha256":"a"*64,
               "evidence_url":"http://evil.example/", "outcome":"success",
               "observed_at":"2030-01-01T00:00:00Z"}
    result = assess_receipt(p, receipt, now=datetime(2026, 11, 5, tzinfo=timezone.utc))
    assert result["status"] == "blocked"
    assert "valid_evidence_url_required" in result["reasons"]
    assert "recent_timezone_aware_observation_required" in result["reasons"]
