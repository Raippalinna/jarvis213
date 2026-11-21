"""Deterministic, offline mission planning and evidence-gated state machine.

The engine schedules *intent*, not external actions. Callers must implement
execution, supply a trusted evidence verifier and obtain real approvals. No
LLM prompt or user utterance is interpreted as a capability or permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable


class MissionError(ValueError):
    """Invalid mission specification or state transition."""


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_VERIFICATION = "awaiting_verification"
    VERIFIED = "verified"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MissionStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class MissionStep:
    step_id: str
    description: str
    depends_on: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    approval_id: str | None = None


@dataclass(frozen=True)
class ExecutionEvidence:
    """Untrusted execution claim until independently validated by the caller."""

    artifact_ref: str
    summary: str


@dataclass
class StepRecord:
    status: StepStatus = StepStatus.PENDING
    evidence: ExecutionEvidence | None = None
    verification_ref: str | None = None
    attempts: int = 0
    failure_reason: str | None = None


class MissionEngine:
    """Pure in-memory orchestration. No network, API calls, persistence or side effects.

    Every step must pass explicit dependency, capability and approval gates.
    'submit()' records a claim; only 'verify()' can mark a step verified.
    The caller's verifier must check evidence against a trusted source.
    """

    def __init__(self, steps: Iterable[MissionStep]):
        ordered = tuple(steps)
        if not ordered:
            raise MissionError("A mission requires at least one step")
        self.steps: dict[str, MissionStep] = {}
        for step in ordered:
            if not isinstance(step, MissionStep):
                raise MissionError("Every step must be a MissionStep")
            if not step.step_id or not step.step_id.strip() or not step.description.strip():
                raise MissionError("Each step needs an ID and description")
            if step.step_id in self.steps:
                raise MissionError("Duplicate step ID")
            if len(set(step.depends_on)) != len(step.depends_on):
                raise MissionError("Duplicate dependency")
            if len(set(step.required_capabilities)) != len(step.required_capabilities):
                raise MissionError("Duplicate capability")
            if any(not value or not value.strip() for value in (*step.depends_on, *step.required_capabilities)):
                raise MissionError("Blank dependency or capability")
            if step.approval_id is not None and not step.approval_id.strip():
                raise MissionError("Blank approval identifier")
            self.steps[step.step_id] = step
        for step in ordered:
            if any(dep not in self.steps for dep in step.depends_on):
                raise MissionError("Unknown dependency")

        # Visit every node and fail closed on cycles. Preserves insertion order.
        marks: dict[str, int] = {}
        topo: list[str] = []

        def visit(step_id: str) -> None:
            if marks.get(step_id) == 1:
                raise MissionError("Cyclic dependency")
            if marks.get(step_id) == 2:
                return
            marks[step_id] = 1
            for dependency in self.steps[step_id].depends_on:
                visit(dependency)
            marks[step_id] = 2
            topo.append(step_id)

        for step_id in self.steps:
            visit(step_id)
        self.order: tuple[str, ...] = tuple(topo)
        self.records: dict[str, StepRecord] = {step_id: StepRecord() for step_id in self.steps}
        self.cancelled = False

    def gate(self, step_id: str, *, capabilities: Iterable[str] = (), approvals: Iterable[str] = ()) -> str:
        """Return a reason (or 'ready') without mutating the mission."""
        step = self.steps[step_id]
        record = self.records[step_id]
        if self.cancelled:
            return "mission_cancelled"
        if record.status != StepStatus.PENDING:
            return f"step_{record.status.value}"
        deps = (self.records[dependency].status for dependency in step.depends_on)
        if any(status in (StepStatus.FAILED, StepStatus.CANCELLED) for status in deps):
            return "dependency_failed"
        if any(status != StepStatus.VERIFIED for status in (self.records[d].status for d in step.depends_on)):
            return "dependency_unverified"
        if not set(step.required_capabilities).issubset(set(capabilities)):
            return "missing_capability"
        if step.approval_id is not None and step.approval_id not in set(approvals):
            return "missing_approval"
        return "ready"

    def ready(self, *, capabilities: Iterable[str] = (), approvals: Iterable[str] = ()) -> tuple[str, ...]:
        available = frozenset(capabilities)
        approved = frozenset(approvals)
        return tuple(
            step_id for step_id in self.order
            if self.gate(step_id, capabilities=available, approvals=approved) == "ready"
        )

    def start(self, step_id: str, *, capabilities: Iterable[str] = (), approvals: Iterable[str] = ()) -> None:
        reason = self.gate(step_id, capabilities=capabilities, approvals=approvals)
        if reason != "ready":
            raise MissionError(f"Step cannot start: {reason}")
        record = self.records[step_id]
        record.status = StepStatus.RUNNING
        record.attempts += 1

    def submit(self, step_id: str, evidence: ExecutionEvidence) -> None:
        """Record execution evidence, never conclude that it is verified."""
        record = self.records[step_id]
        if self.cancelled or record.status != StepStatus.RUNNING:
            raise MissionError("Step is not running")
        if not isinstance(evidence, ExecutionEvidence) or not evidence.artifact_ref.strip() or not evidence.summary.strip():
            record.status = StepStatus.FAILED
            record.failure_reason = "missing_execution_evidence"
            raise MissionError("Missing execution evidence")
        record.evidence = evidence
        record.status = StepStatus.AWAITING_VERIFICATION

    def verify(self, step_id: str, verifier: Callable[[ExecutionEvidence], str | None]) -> bool:
        """Verify using a caller-owned trusted check that returns a nonblank proof ref.

        A returned proof reference MUST correspond to a successful external check.
        No verifier is supplied by this engine, so it cannot self-attest.
        """
        record = self.records[step_id]
        if self.cancelled or record.status != StepStatus.AWAITING_VERIFICATION or record.evidence is None:
            raise MissionError("Step is not awaiting verification")
        try:
            proof = verifier(record.evidence)
        except Exception:
            proof = None  # Do not expose verifier exceptions or potential secrets.
        if not isinstance(proof, str) or not proof.strip():
            record.status = StepStatus.FAILED
            record.failure_reason = "verification_failed"
            return False
        record.verification_ref = proof.strip()
        record.status = StepStatus.VERIFIED
        return True

    def fail(self, step_id: str, *, reason: str = "execution_failed") -> None:
        record = self.records[step_id]
        if self.cancelled or record.status not in (StepStatus.RUNNING, StepStatus.AWAITING_VERIFICATION):
            raise MissionError("Step is not active")
        record.status = StepStatus.FAILED
        # Store only a bounded machine code; no raw provider errors or tokens.
        record.failure_reason = reason if reason in {
            "execution_failed", "timeout", "provider_unavailable", "primary_failed"
        } else "execution_failed"

    def retry(self, step_id: str) -> None:
        """Manual retry/fallback: execution remains the caller's responsibility."""
        record = self.records[step_id]
        if self.cancelled or record.status != StepStatus.FAILED:
            raise MissionError("Only failed steps can be retried")
        record.status = StepStatus.PENDING
        record.failure_reason = None
        record.evidence = None
        record.verification_ref = None

    def cancel(self) -> None:
        self.cancelled = True
        for record in self.records.values():
            if record.status not in (StepStatus.VERIFIED, StepStatus.FAILED):
                record.status = StepStatus.CANCELLED

    @property
    def status(self) -> MissionStatus:
        if self.cancelled:
            return MissionStatus.CANCELLED
        values = [record.status for record in self.records.values()]
        if all(s == StepStatus.VERIFIED for s in values):
            return MissionStatus.VERIFIED
        if any(s == StepStatus.FAILED for s in values):
            return MissionStatus.FAILED
        if any(s != StepStatus.PENDING for s in values):
            return MissionStatus.IN_PROGRESS
        return MissionStatus.PLANNED

    def snapshot(self) -> dict:
        """Serializable, non-sensitive summary. No output bodies or secrets."""
        return {
            "status": self.status.value,
            "steps": {
                step_id: {
                    "status": record.status.value,
                    "attempts": record.attempts,
                    "verified": record.status == StepStatus.VERIFIED,
                    "evidence_recorded": record.evidence is not None,
                    "verification_recorded": record.verification_ref is not None,
                    "failure_reason": record.failure_reason,
                }
                for step_id, record in self.records.items()
            },
        }
