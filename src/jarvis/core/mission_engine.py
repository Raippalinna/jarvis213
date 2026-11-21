"""Deterministic, offline mission queue for JARVIS.

This is a scheduling/state-machine primitive, NOT a worker. No model or tool
is executed. An external, trusted execution layer must enforce its own risk
classification, authorization, idempotency and approval checks before effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


RISK_CLASSES = frozenset({"R0", "R1", "R2", "R3"})
_TERMINAL = frozenset({"completed", "failed", "cancelled"})
_MAX_STEPS = 32


@dataclass(frozen=True)
class Step:
    step_id: str
    action: str
    depends_on: tuple[str, ...] = ()
    risk_class: str = "R2"  # unknown actions fail closed by default
    max_attempts: int = 1


@dataclass
class _Progress:
    status: str = "pending"
    attempts: int = 0


@dataclass
class MissionQueue:
    """Single-mission state machine. All calls are in-memory and side-effect free.

    `approval_check` MUST be supplied by the trusted caller for R2/R3 actions.
    It is called at claim time; approvals are not cached or serialized.
    A claim is a proposed work lease, not permission to perform the work.
    After crash/restart, do not replay an in-flight action without external
    reconciliation of its idempotency key and actual outcome.
    """

    mission_id: str
    steps: tuple[Step, ...]
    _progress: dict[str, _Progress] = field(init=False, repr=False)
    _events: list[dict] = field(init=False, repr=False)
    _cancelled: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, str) or not self.mission_id.strip() or len(self.mission_id) > 100:
            raise ValueError("invalid_mission_id")
        if not isinstance(self.steps, tuple) or not 1 <= len(self.steps) <= _MAX_STEPS:
            raise ValueError("invalid_step_count")
        ids: set[str] = set()
        for step in self.steps:
            if not isinstance(step, Step):
                raise ValueError("invalid_step")
            if (not isinstance(step.step_id, str) or not step.step_id.strip()
                    or len(step.step_id) > 80 or step.step_id in ids):
                raise ValueError("invalid_step_id")
            if not isinstance(step.action, str) or not step.action.strip() or len(step.action) > 500:
                raise ValueError("invalid_action")
            if step.risk_class not in RISK_CLASSES:
                raise ValueError("invalid_risk_class")
            if type(step.max_attempts) is not int or not 1 <= step.max_attempts <= 3:
                raise ValueError("invalid_attempt_limit")
            if not isinstance(step.depends_on, tuple) or any(not isinstance(d, str) for d in step.depends_on):
                raise ValueError("invalid_dependencies")
            if len(step.depends_on) != len(set(step.depends_on)):
                raise ValueError("duplicate_dependency")
            ids.add(step.step_id)
        graph = {s.step_id: s.depends_on for s in self.steps}
        for sid, deps in graph.items():
            if sid in deps or any(dep not in graph for dep in deps):
                raise ValueError("missing_or_self_dependency")
        visited: set[str] = set()
        active: set[str] = set()

        def visit(sid: str) -> None:
            if sid in active:
                raise ValueError("dependency_cycle")
            if sid in visited:
                return
            active.add(sid)
            for dep in graph[sid]:
                visit(dep)
            active.remove(sid)
            visited.add(sid)

        for sid in graph:
            visit(sid)
        self._progress = {sid: _Progress() for sid in graph}
        self._events = [{"event": "created", "mission_id": self.mission_id}]

    def _get(self, step_id: str) -> tuple[Step, _Progress]:
        for step in self.steps:
            if step.step_id == step_id:
                return step, self._progress[step_id]
        raise KeyError("unknown_step")

    def status(self, step_id: str) -> str:
        step, progress = self._get(step_id)
        if progress.status != "pending":
            return progress.status
        if self._cancelled:
            return "cancelled"
        if any(self.status(dep) in {"failed", "blocked", "cancelled"} for dep in step.depends_on):
            return "blocked"
        if step.risk_class in {"R2", "R3"} and all(
            self.status(dep) == "completed" for dep in step.depends_on
        ):
            return "approval_required"
        return "pending"  # pending may be ready; caller uses ready()

    def ready(self) -> list[str]:
        """List dependency-ready steps, including approval-required tasks for review."""
        if self._cancelled:
            return []
        return [s.step_id for s in self.steps
                if self._progress[s.step_id].status == "pending"
                and all(self.status(dep) == "completed" for dep in s.depends_on)]

    def claim(self, step_id: str, *, approval_check: Callable[[str, str], bool] | None = None) -> dict:
        """Reserve an action; never execute it. Caller must verify authority separately."""
        step, progress = self._get(step_id)
        if self._cancelled or progress.status != "pending" or step_id not in self.ready():
            raise RuntimeError("step_not_ready")
        if step.risk_class in {"R2", "R3"}:
            if approval_check is None or approval_check(step.step_id, step.risk_class) is not True:
                raise PermissionError("approval_not_verified")
        progress.attempts += 1
        progress.status = "running"
        self._events.append({"event": "claimed", "step_id": step_id, "attempt": progress.attempts})
        return {"mission_id": self.mission_id, "step_id": step_id,
                "attempt": progress.attempts, "action": step.action,
                "risk_class": step.risk_class}

    def finish(self, step_id: str, attempt: int, *, success: bool) -> str:
        """Record outcome of an externally verified run; no arbitrary result/error stored."""
        step, progress = self._get(step_id)
        if type(attempt) is not int or progress.status != "running" or progress.attempts != attempt:
            raise RuntimeError("stale_or_invalid_completion")
        if type(success) is not bool:
            raise ValueError("invalid_success")
        progress.status = "completed" if success else (
            "pending" if progress.attempts < step.max_attempts else "failed"
        )
        self._events.append({"event": "completed" if success else "attempt_failed",
                             "step_id": step_id, "attempt": attempt})
        return progress.status

    def cancel(self) -> None:
        if self._cancelled:
            return
        self._cancelled = True
        for progress in self._progress.values():
            if progress.status not in _TERMINAL:
                progress.status = "cancelled"
        self._events.append({"event": "cancelled", "mission_id": self.mission_id})

    def snapshot(self) -> dict:
        """Sanitized operational view, without approval tokens, model output or secrets."""
        return {
            "mission_id": self.mission_id,
            "cancelled": self._cancelled,
            "steps": [{"step_id": s.step_id,
                       "depends_on": list(s.depends_on), "risk_class": s.risk_class,
                       "max_attempts": s.max_attempts,
                       "attempts": self._progress[s.step_id].attempts,
                       "status": self.status(s.step_id)} for s in self.steps],
            "events": [dict(e) for e in self._events],
        }
