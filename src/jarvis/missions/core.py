"""Deterministisk Mission Engine v0.1.

Endast planer och granskningskontrakt: inga agentkörningar, nätanrop,
verktygsanrop, filskrivningar eller ändringar av produktionsmiljö.
En tillgänglig connector är INTE bevis på att ett uppdrag har utförts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from urllib.parse import urlsplit
from typing import Any, Mapping

VERSION = "mission-plan/v1"
_CONNECTORS = frozenset({"firecrawl", "notion", "github", "higgsfield", "slack", "vercel"})
_SENSITIVITY = frozenset({"public", "internal", "confidential", "secret"})
_HASH = re.compile(r"^[0-9a-f]{64}$")

# Ordning och ansvar är explicita; modellen får aldrig själv utöka behörigheter.
_STAGES = (
    ("intake", "strategist", None, "local", ()),
    ("research", "researcher", "firecrawl", "external_read", ("intake",)),
    ("evidence", "verifier", None, "local", ("research",)),
    ("architecture", "architect", None, "local", ("evidence",)),
    ("implementation", "coder", "github", "external_write", ("architecture",)),
    ("testing", "tester", None, "local", ("implementation",)),
    ("review", "independent_reviewer", None, "local", ("testing",)),
    ("release", "release_manager", "vercel", "external_publish", ("review",)),
)


def _valid_goal(goal: Any) -> bool:
    return (isinstance(goal, str) and 4 <= len(goal.strip()) <= 4000
            and not any(ord(ch) < 32 for ch in goal if ch not in "\n\t"))


def plan_mission(
    goal: str,
    *,
    connector_statuses: Mapping[str, str] | None = None,
    sensitivity: str = "internal",
    public_query_reviewed: bool = False,
    mode: str = "dry_run",
    cancelled: bool = False,
) -> dict[str, Any]:
    """Planera utan att skicka uppgiftsinnehåll till extern connector.

    Endast connectorstatus 'e2e_verified' anses operativt tillgänglig.
    Utdata saknar uppgiftens råtext; endast en deterministisk fingerprint visas.
    Det finns ingen execute-funktion i denna modul.
    """
    if cancelled is True:
        return {"status": "cancelled", "execution_allowed": False, "steps": []}
    if not _valid_goal(goal):
        return {"status": "blocked", "reasons": ["invalid_goal"], "execution_allowed": False, "steps": []}
    if mode != "dry_run":
        return {"status": "blocked", "reasons": ["only_dry_run_supported"], "execution_allowed": False, "steps": []}
    if sensitivity not in _SENSITIVITY:
        return {"status": "blocked", "reasons": ["invalid_sensitivity"], "execution_allowed": False, "steps": []}
    if type(public_query_reviewed) is not bool or type(cancelled) is not bool:
        return {"status": "blocked", "reasons": ["invalid_policy_input"], "execution_allowed": False, "steps": []}
    if connector_statuses is None:
        connector_statuses = {}
    if not isinstance(connector_statuses, Mapping) or any(
        name not in _CONNECTORS or status not in {"e2e_verified", "unverified", "disconnected"}
        for name, status in connector_statuses.items()
    ):
        return {"status": "blocked", "reasons": ["invalid_connector_status"], "execution_allowed": False, "steps": []}

    normalized = " ".join(goal.split())
    digest = sha256((VERSION + "\n" + normalized).encode("utf-8")).hexdigest()
    steps = []
    for sid, role, connector, risk, deps in _STAGES:
        reasons: list[str] = []
        if connector and connector_statuses.get(connector) != "e2e_verified":
            reasons.append("connector_not_e2e_verified")
        if sid == "research" and not public_query_reviewed:
            # Även publika uppdrag får inte skickas externt automatiskt.
            reasons.append("public_query_not_reviewed")
        if risk in {"external_write", "external_publish"}:
            reasons.append("explicit_action_approval_required")
        steps.append({
            "id": sid, "role": role, "connector": connector,
            "risk": risk, "depends_on": list(deps),
            "status": "blocked" if reasons else "planned",
            "blocking_reasons": reasons, "executed": False,
            "evidence": "not_collected", "cost_sek": None,
        })
    # Tillval planeras men aktiveras aldrig av nyckelord ens om verktyg finns.
    optional = []
    if re.search(r"\b(video|reklam|film|higgsfield|kreativ)\b", normalized, re.I):
        optional.append(("creative", "creative_director", "higgsfield", "external_spend", ("architecture",)))
    if re.search(r"\b(slack|meddela|rapportera|notifiera)\b", normalized, re.I):
        optional.append(("notify", "operations", "slack", "external_send", ("review",)))
    for sid, role, connector, risk, deps in optional:
        reasons = ["explicit_action_approval_required", "cost_or_scope_review_required"] if risk == "external_spend" else ["explicit_action_approval_required"]
        if connector_statuses.get(connector) != "e2e_verified":
            reasons.insert(0, "connector_not_e2e_verified")
        steps.append({"id": sid, "role": role, "connector": connector,
                      "risk": risk, "depends_on": list(deps), "status": "blocked",
                      "blocking_reasons": reasons, "executed": False,
                      "evidence": "not_collected", "cost_sek": None})

    return {
        "status": "prepared", "schema": VERSION,
        "mission_id": digest[:20], "goal_sha256": digest,
        "sensitivity": sensitivity, "mode": "dry_run",
        "execution_allowed": False, "agents_executed": 0,
        "external_calls": 0, "cost_sek": 0,
        "steps": steps,
        "disclaimer": "Plan, inte utförande; connectorstatus är indata, inte uppmätt av motorn.",
    }


def assess_receipt(plan: object, receipt: object, *, now: datetime | None = None) -> dict[str, Any]:
    """Bedöm formell evidens, utan att hävda att den externa källan verifierats.

    Avsedd för senare externt autentiserad läsback och oberoende granskning.
    En modell kan inte själv göra en status 'done' med detta API.
    """
    reasons: list[str] = []
    if not isinstance(plan, dict) or plan.get("schema") != VERSION or plan.get("execution_allowed") is not False:
        return {"status": "blocked", "reasons": ["valid_plan_required"], "externally_verified": False}
    if not isinstance(receipt, dict):
        return {"status": "blocked", "reasons": ["receipt_required"], "externally_verified": False}
    steps = {x.get("id"): x for x in plan.get("steps", []) if isinstance(x, dict)}
    sid = receipt.get("step_id")
    step = steps.get(sid) if isinstance(sid, str) else None
    if step is None:
        reasons.append("unknown_step")
    if receipt.get("mission_id") != plan.get("mission_id"):
        reasons.append("mission_mismatch")
    digest = receipt.get("artifact_sha256")
    if not isinstance(digest, str) or not _HASH.fullmatch(digest):
        reasons.append("artifact_sha256_required")
    url = receipt.get("evidence_url")
    if not isinstance(url, str) or len(url) > 2048:
        reasons.append("valid_evidence_url_required")
    else:
        try:
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.port not in (None, 443)):
                reasons.append("valid_evidence_url_required")
        except ValueError:
            reasons.append("valid_evidence_url_required")
    if receipt.get("outcome") != "success":
        reasons.append("successful_outcome_required")
    clock = datetime.now(timezone.utc) if now is None else now
    try:
        stamp = datetime.fromisoformat(str(receipt.get("observed_at", "")).replace("Z", "+00:00"))
        if stamp.tzinfo is None or clock.tzinfo is None or stamp > clock or clock - stamp > timedelta(days=30):
            reasons.append("recent_timezone_aware_observation_required")
    except (ValueError, TypeError):
        reasons.append("recent_timezone_aware_observation_required")
    if step and step.get("risk") in {"external_write", "external_publish", "external_send", "external_spend"}:
        if receipt.get("approval_reference") in (None, "", False):
            reasons.append("independent_approval_reference_required")
    return {"status": "eligible_for_external_review" if not reasons else "blocked",
            "reasons": reasons, "externally_verified": False, "mission_completed": False}
