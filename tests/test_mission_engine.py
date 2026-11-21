"""Offline-only MissionQueue tests: no models, network, secrets or side effects."""
import pytest

from jarvis.core.mission_engine import MissionQueue, Step


def test_dependencies_and_order():
    mission = MissionQueue("m1", (
        Step("read", "Inspect source", risk_class="R0"),
        Step("build", "Propose patch", ("read",), risk_class="R1"),
        Step("notify", "Send externally", ("build",), risk_class="R2"),
    ))
    assert mission.ready() == ["read"]
    assert mission.claim("read")["attempt"] == 1
    assert mission.ready() == []
    assert mission.finish("read", 1, success=True) == "completed"
    assert mission.ready() == ["build"]
    mission.claim("build")
    mission.finish("build", 1, success=True)
    assert mission.ready() == ["notify"]
    assert mission.status("notify") == "approval_required"
    with pytest.raises(PermissionError):
        mission.claim("notify")
    assert mission.status("notify") == "approval_required"
    with pytest.raises(PermissionError):
        mission.claim("notify", approval_check=lambda *_: False)
    lease = mission.claim("notify", approval_check=lambda sid, risk: (sid, risk) == ("notify", "R2"))
    assert lease["risk_class"] == "R2"
    assert mission.finish("notify", lease["attempt"], success=True) == "completed"
    assert mission.ready() == []


def test_default_risk_is_blocked_without_external_verifier():
    mission = MissionQueue("m", (Step("unknown", "External work"),))
    assert mission.status("unknown") == "approval_required"
    with pytest.raises(PermissionError, match="approval_not_verified"):
        mission.claim("unknown")
    assert mission.snapshot()["steps"][0]["attempts"] == 0


def test_retry_bounded_and_dependent_blocked():
    mission = MissionQueue("m", (
        Step("a", "safe", risk_class="R0", max_attempts=2),
        Step("b", "child", ("a",), risk_class="R0"),
        Step("c", "grandchild", ("b",), risk_class="R0"),
    ))
    first = mission.claim("a")
    assert mission.finish("a", first["attempt"], success=False) == "pending"
    assert mission.ready() == ["a"]
    second = mission.claim("a")
    with pytest.raises(RuntimeError, match="stale_or_invalid_completion"):
        mission.finish("a", first["attempt"], success=True)
    assert mission.finish("a", second["attempt"], success=False) == "failed"
    assert mission.status("b") == "blocked"
    assert mission.status("c") == "blocked"
    assert mission.ready() == []


def test_cancellation_is_idempotent_and_stale_completion_rejected():
    mission = MissionQueue("m", (Step("a", "work", risk_class="R0"),))
    lease = mission.claim("a")
    mission.cancel()
    mission.cancel()
    assert mission.status("a") == "cancelled"
    assert mission.ready() == []
    with pytest.raises(RuntimeError):
        mission.finish("a", lease["attempt"], success=True)
    with pytest.raises(RuntimeError):
        mission.claim("a")
    assert sum(e["event"] == "cancelled" for e in mission.snapshot()["events"]) == 1


@pytest.mark.parametrize("steps", [
    (),
    (Step("a", "work"), Step("a", "duplicate")),
    (Step("a", "work", ("missing",)),),
    (Step("a", "work", ("a",)),),
    (Step("a", "work", ("b",)), Step("b", "work", ("a",))),
    (Step("a", "work", risk_class="R9"),),
    (Step("a", "work", max_attempts=0),),
    (Step("a", "work", max_attempts=True),),
    (Step("a", "work", depends_on=["missing"]),),
    (Step("a", "work", depends_on=("a", "a")),),
])
def test_invalid_plans_fail_closed(steps):
    with pytest.raises(ValueError):
        MissionQueue("m", steps)


def test_external_callback_not_executed_on_planning_or_snapshot():
    mission = MissionQueue("m", (Step("a", "Do not execute", risk_class="R3"),))
    assert mission.ready() == ["a"]
    assert mission.snapshot()["steps"][0]["status"] == "approval_required"
    assert mission.snapshot()["events"] == [{"event": "created", "mission_id": "m"}]


def test_duplicate_finish_and_invalid_boolean_rejected():
    mission = MissionQueue("m", (Step("a", "work", risk_class="R0"),))
    lease = mission.claim("a")
    with pytest.raises(ValueError):
        mission.finish("a", lease["attempt"], success=1)
    assert mission.finish("a", lease["attempt"], success=True) == "completed"
    with pytest.raises(RuntimeError):
        mission.finish("a", lease["attempt"], success=True)
