"""Policy-gated agent roster and orchestration for the main JARVIS mission engine.

This module deliberately has no HTTP clients or provider credentials. Production
adapters must independently authenticate capabilities, approvals and evidence,
and enforce provider-side spending limits. No model text grants privileges.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from secrets import token_hex
from typing import Callable, Iterable, Mapping

from .mission_engine import ExecutionEvidence, MissionEngine, MissionError, MissionStep


class OrchestrationError(ValueError):
    """Invalid orchestration request or unavailable safety requirement."""


@dataclass(frozen=True)
class AgentSpec:
    role: str
    risk: str
    capability: str | None
    approval_required: bool
    estimated_cost_sek: Decimal


@dataclass(frozen=True)
class AgentTask:
    step_id: str
    role: str
    description: str
    depends_on: tuple[str, ...] = ()


# This is an allowlist of intended roles, NOT a list of live or connected agents.
# Cost reservations are conservative placeholders, not provider quotes.
AGENTS: Mapping[str, AgentSpec] = {
    "strategist": AgentSpec("strategist", "local", None, False, Decimal("0")),
    "researcher": AgentSpec("researcher", "external_read", "reviewed_research_query", True, Decimal("0.10")),
    "verifier": AgentSpec("verifier", "local", "trusted_source_read", False, Decimal("0")),
    "architect": AgentSpec("architect", "local", None, False, Decimal("0")),
    "coder": AgentSpec("coder", "external_write", "repo_branch_write", True, Decimal("0.10")),
    "tester": AgentSpec("tester", "local", "offline_test", False, Decimal("0")),
    "independent_reviewer": AgentSpec("independent_reviewer", "local", "review_read", False, Decimal("0")),
    "release_manager": AgentSpec("release_manager", "external_publish", "deploy", True, Decimal("0.10")),
    "creative_director": AgentSpec("creative_director", "external_spend", "creative_provider", True, Decimal("0.10")),
    "operations": AgentSpec("operations", "external_send", "notification_send", True, Decimal("0.10")),
}

_BASE = (
    AgentTask("intake", "strategist", "Validate scope and non-sensitive objective"),
    AgentTask("research", "researcher", "Research with separately reviewed public query", ("intake",)),
    AgentTask("evidence", "verifier", "Independently evaluate retrieved sources", ("research",)),
    AgentTask("architecture", "architect", "Define interfaces, safety boundaries and work packages", ("evidence",)),
    AgentTask("implementation", "coder", "Propose changes on a reviewable branch", ("architecture",)),
    AgentTask("testing", "tester", "Run fixed offline regression suite", ("implementation",)),
    AgentTask("review", "independent_reviewer", "Review tests, evidence and release risk", ("testing",)),
    AgentTask("release", "release_manager", "Release only after authenticated human approval", ("review",)),
)


def _money(value: str | Decimal) -> Decimal:
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise OrchestrationError("invalid_budget") from None
    if not amount.is_finite() or amount < 0 or amount > Decimal("200"):
        raise OrchestrationError("invalid_budget")
    return amount


class AgentOrchestrator:
    """Deterministic DAG with no automatic tool discovery or privilege escalation.

    Production calls are disabled by default. A trusted caller must supply
    authenticated capability and approval *results*, a role-matched executor,
    and a verifier backed by an INDEPENDENT authoritative readback. The
    orchestrator cannot prove that the caller's callbacks are trustworthy.
    State is volatile; durable idempotency/audit must precede deployment.
    """

    def __init__(
        self,
        goal: str,
        *,
        creative: bool = False,
        notifications: bool = False,
        budget_sek: str | Decimal = "0",
        execution_enabled: bool = False,
    ):
        if not isinstance(goal, str) or not 4 <= len(goal.strip()) <= 4000:
            raise OrchestrationError("invalid_goal")
        if any(ord(char) < 32 for char in goal if char not in "\n\t"):
            raise OrchestrationError("invalid_goal")
        if type(creative) is not bool or type(notifications) is not bool:
            raise OrchestrationError("invalid_options")
        if type(execution_enabled) is not bool:
            raise OrchestrationError("invalid_execution_mode")

        self.mission_id = token_hex(12)  # Opaque random identifier; no sensitive goal hashes in UI.
        self.execution_enabled = execution_enabled
        self.budget_sek = _money(budget_sek)
        self.reserved_sek = Decimal("0")
        tasks = list(_BASE)
        if creative:
            tasks.append(AgentTask("creative", "creative_director", "Create draft media for review", ("architecture",)))
            tasks = [
                AgentTask(task.step_id, task.role, task.description, ("testing", "creative"))
                if task.step_id == "review" else task
                for task in tasks
            ]
        if notifications:
            tasks.append(AgentTask("notification", "operations", "Send approved status notification", ("review",)))

        self.tasks: dict[str, AgentTask] = {task.step_id: task for task in tasks}
        self.engine = MissionEngine([
            MissionStep(
                task.step_id,
                task.description,
                depends_on=task.depends_on,
                required_capabilities=((AGENTS[task.role].capability,) if AGENTS[task.role].capability else ()),
                approval_id=(self.approval_id(task.step_id) if AGENTS[task.role].approval_required else None),
            )
            for task in tasks
        ])

    def approval_id(self, step_id: str) -> str:
        """Identifier for a backend-approved action, never a grant in itself."""
        if step_id not in ("research", "implementation", "release", "creative", "notification"):
            raise OrchestrationError("unknown_approval_action")
        return self.mission_id + ":" + step_id

    def snapshot(self) -> dict:
        """Safe UI representation: never return the original goal, secrets or evidence."""
        data = self.engine.snapshot()
        data.update({
            "schema": "jarvis-agent-orchestration/v1",
            "mission_id": self.mission_id,
            "execution_enabled": self.execution_enabled,
            "budget_sek": str(self.budget_sek),
            "reserved_sek": str(self.reserved_sek),
            "agents": {
                name: {
                    "role": task.role,
                    "risk": AGENTS[task.role].risk,
                    "requires_approval": AGENTS[task.role].approval_required,
                    "required_capability": AGENTS[task.role].capability,
                    "depends_on": list(task.depends_on),
                    "gate": "execution_disabled" if not self.execution_enabled else "requires_trusted_runtime_checks",
                }
                for name, task in self.tasks.items()
            },
            "production_verified": False,
        })
        return data

    def run_one(
        self,
        step_id: str,
        *,
        adapter_role: str,
        execute: Callable[[AgentTask], ExecutionEvidence],
        verify: Callable[[ExecutionEvidence], str | None],
        autonomy_check: Callable[[str], bool] | None = None,
        capability_check: Callable[[str, str, str], bool] | None = None,
        approval_check: Callable[[str, str, str], bool] | None = None,
        spend_check: Callable[[str, str, Decimal], bool] | None = None,
    ) -> bool:
        """Invoke one step only after independent trusted policy readbacks.

        These callbacks MUST be implemented by a backend with an authenticated
        principal and tenant, not accepted from an HTTP user or an LLM. The
        runtime also needs durable idempotency and provider-side spend limits.
        """

        def trusted(check, *args) -> bool:
            if not callable(check):
                return False
            try:
                return check(*args) is True
            except Exception:
                return False  # No raw error, stale policy or fail-open behavior.

        if not self.execution_enabled:
            raise OrchestrationError("execution_disabled")
        if step_id not in self.tasks:
            raise OrchestrationError("unknown_step")
        task = self.tasks[step_id]
        spec = AGENTS[task.role]
        if adapter_role != task.role:
            raise OrchestrationError("agent_role_mismatch")
        if not callable(execute) or not callable(verify):
            raise OrchestrationError("missing_trusted_adapter")
        if not trusted(autonomy_check, self.mission_id):
            raise OrchestrationError("trusted_autonomy_check_required")

        # Untrusted strings are not credentials or approvals. The backend
        # independently checks authenticated capability and action decisions.
        caps: tuple[str, ...] = ()
        approvals: tuple[str, ...] = ()
        if spec.capability:
            if not trusted(capability_check, self.mission_id, step_id, spec.capability):
                raise OrchestrationError("trusted_capability_required")
            caps = (spec.capability,)
        if spec.approval_required:
            approval_id = self.approval_id(step_id)
            if not trusted(approval_check, self.mission_id, step_id, approval_id):
                raise OrchestrationError("trusted_approval_required")
            approvals = (approval_id,)
        if self.reserved_sek + spec.estimated_cost_sek > self.budget_sek:
            raise OrchestrationError("budget_exceeded")
        if spec.estimated_cost_sek and not trusted(
            spend_check, self.mission_id, step_id, spec.estimated_cost_sek
        ):
            raise OrchestrationError("trusted_spend_limit_required")

        self.engine.start(step_id, capabilities=caps, approvals=approvals)
        # Reserve even if execution fails: a failed provider call may still cost.
        self.reserved_sek += spec.estimated_cost_sek
        try:
            evidence = execute(task)
            self.engine.submit(step_id, evidence)
        except Exception:
            if self.engine.records[step_id].status.value == "running":
                self.engine.fail(step_id, reason="execution_failed")
            return False
        return self.engine.verify(step_id, verify)

    def retry(self, step_id: str, *, operator_approved: bool = False) -> None:
        """Manual-only retry with a bounded maximum of two attempts per step."""
        if operator_approved is not True:
            raise OrchestrationError("manual_retry_approval_required")
        if step_id not in self.tasks:
            raise OrchestrationError("unknown_step")
        if self.engine.records[step_id].attempts >= 2:
            raise OrchestrationError("retry_limit_reached")
        self.engine.retry(step_id)

    def cancel(self) -> None:
        self.engine.cancel()
