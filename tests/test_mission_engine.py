"""Key-free regression tests for Jarvis's deterministic mission gates."""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from jarvis.core.mission_engine import (  # noqa: E402
    ExecutionEvidence,
    MissionEngine,
    MissionError,
    MissionStatus,
    MissionStep,
    StepStatus,
)


def simple_mission():
    return MissionEngine([
        MissionStep("inspect", "Inspect repository"),
        MissionStep("patch", "Propose patch", depends_on=("inspect",), required_capabilities=("repo_read",)),
        MissionStep("deploy", "Deploy", depends_on=("patch",), required_capabilities=("deploy",), approval_id="owner_deploy"),
    ])


def finish(engine, step, ref="ci:123"):
    engine.submit(step, ExecutionEvidence("artifact:test", "Test passed"))
    assert engine.verify(step, lambda evidence: ref if evidence.artifact_ref == "artifact:test" else None)


def test_success_requires_verified_evidence_for_each_dependency():
    engine = simple_mission()
    assert engine.ready() == ("inspect",)
    engine.start("inspect")
    assert engine.status == MissionStatus.IN_PROGRESS
    assert engine.ready(capabilities=("repo_read",)) == ()
    engine.submit("inspect", ExecutionEvidence("artifact:test", "Found files"))
    assert engine.gate("patch", capabilities=("repo_read",)) == "dependency_unverified"
    assert engine.status != MissionStatus.VERIFIED
    assert engine.verify("inspect", lambda _: "trusted:inspect")
    assert engine.ready(capabilities=("repo_read",)) == ("patch",)
    engine.start("patch", capabilities=("repo_read",))
    finish(engine, "patch")
    assert engine.gate("deploy", capabilities=("deploy",)) == "missing_approval"
    engine.start("deploy", capabilities=("deploy",), approvals=("owner_deploy",))
    finish(engine, "deploy")
    assert engine.status == MissionStatus.VERIFIED
    assert engine.snapshot()["steps"]["deploy"]["verification_recorded"] is True


def test_unknown_dependency_rejected():
    with pytest.raises(MissionError, match="Unknown dependency"):
        MissionEngine([MissionStep("a", "A", depends_on=("missing",))])


def test_cycle_rejected():
    with pytest.raises(MissionError, match="Cyclic"):
        MissionEngine([MissionStep("a", "A", depends_on=("b",)), MissionStep("b", "B", depends_on=("a",))])


def test_duplicate_id_rejected():
    with pytest.raises(MissionError, match="Duplicate"):
        MissionEngine([MissionStep("a", "A"), MissionStep("a", "B")])


def test_empty_mission_rejected():
    with pytest.raises(MissionError, match="at least"):
        MissionEngine([])


def test_capability_and_approval_must_be_supplied_explicitly():
    engine = simple_mission()
    engine.start("inspect")
    finish(engine, "inspect")
    assert engine.gate("patch") == "missing_capability"
    with pytest.raises(MissionError, match="missing_capability"):
        engine.start("patch")
    engine.start("patch", capabilities=("repo_read",))
    finish(engine, "patch")
    with pytest.raises(MissionError, match="missing_approval"):
        engine.start("deploy", capabilities=("deploy",))
    assert engine.status != MissionStatus.VERIFIED


def test_bad_or_empty_execution_evidence_fails_closed():
    engine = MissionEngine([MissionStep("a", "A")])
    engine.start("a")
    with pytest.raises(MissionError, match="Missing execution"):
        engine.submit("a", ExecutionEvidence("", ""))
    assert engine.status == MissionStatus.FAILED
    assert engine.records["a"].status == StepStatus.FAILED


def test_rejected_evidence_blocks_downstream():
    engine = MissionEngine([MissionStep("a", "A"), MissionStep("b", "B", depends_on=("a",))])
    engine.start("a")
    engine.submit("a", ExecutionEvidence("untrusted:url", "Claim"))
    assert not engine.verify("a", lambda _: None)
    assert engine.gate("b") == "dependency_failed"
    assert engine.status == MissionStatus.FAILED


def test_verifier_exception_masks_exception_and_fails_closed():
    engine = MissionEngine([MissionStep("a", "A")])
    engine.start("a")
    engine.submit("a", ExecutionEvidence("artifact", "result"))

    def verifier(_):
        raise RuntimeError("sensitive external response")

    assert not engine.verify("a", verifier)
    assert "sensitive" not in repr(engine.snapshot())


def test_fallback_by_manual_retry_never_self_attests():
    engine = MissionEngine([MissionStep("a", "A")])
    engine.start("a")
    engine.fail("a", reason="primary_failed")
    assert engine.status == MissionStatus.FAILED
    engine.retry("a")
    assert engine.status == MissionStatus.PLANNED
    engine.start("a")
    engine.submit("a", ExecutionEvidence("fallback:artifact", "Fallback result"))
    assert engine.status != MissionStatus.VERIFIED
    assert engine.verify("a", lambda x: "review:fallback" if x.artifact_ref == "fallback:artifact" else None)
    assert engine.records["a"].attempts == 2
    assert engine.status == MissionStatus.VERIFIED


def test_cancelled_mission_cannot_start_or_verify():
    engine = MissionEngine([MissionStep("a", "A"), MissionStep("b", "B")])
    engine.start("a")
    engine.cancel()
    assert engine.status == MissionStatus.CANCELLED
    assert engine.records["a"].status == StepStatus.CANCELLED
    with pytest.raises(MissionError):
        engine.start("b")
    with pytest.raises(MissionError):
        engine.submit("a", ExecutionEvidence("x", "x"))


def test_not_startable_twice_or_verify_before_submit():
    engine = MissionEngine([MissionStep("a", "A")])
    engine.start("a")
    with pytest.raises(MissionError, match="step_running"):
        engine.start("a")
    with pytest.raises(MissionError, match="not awaiting verification"):
        engine.verify("a", lambda _: "any")


def test_topological_order_does_not_depend_on_input_sequence():
    engine = MissionEngine([MissionStep("third", "Third", depends_on=("second",)), MissionStep("second", "Second", depends_on=("first",)), MissionStep("first", "First")])
    assert engine.order == ("first", "second", "third")
    assert engine.ready() == ("first",)


def test_empty_verification_reference_does_not_mark_done():
    engine = MissionEngine([MissionStep("a", "A")])
    engine.start("a")
    engine.submit("a", ExecutionEvidence("artifact", "result"))
    assert not engine.verify("a", lambda _: "   ")
    assert engine.status == MissionStatus.FAILED


def test_snapshot_never_exposes_evidence_or_untrusted_errors():
    engine = MissionEngine([MissionStep("a", "A")])
    engine.start("a")
    engine.submit("a", ExecutionEvidence("https://secret.invalid/?token=private_value", "Sensitive body"))
    engine.fail("a", reason="SECRET_API_KEY=private_value")
    report = repr(engine.snapshot())
    assert "private_value" not in report
    assert "Sensitive body" not in report
    assert "execution_failed" in report
