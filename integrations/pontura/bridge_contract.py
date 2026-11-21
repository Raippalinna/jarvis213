"""Project-scoped, offline Pontura handoff validator (no network or secrets).

Never treat an origin label or a GitHub link as an authentication proof.
This helper returns a draft only. Its output must not directly invoke Jarvis.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re

ACTIONS = frozenset({"source_review", "maintenance_summary", "opportunity_assessment", "cost_estimate"})
SENSITIVITY = frozenset({"public", "internal"})
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
REQUIRED = frozenset({"contract_version", "origin", "project", "tenant_id", "request_id", "action",
                      "source_ids", "sensitivity", "estimated_cost_sek", "status", "provenance"})

class IntegrationDenied(ValueError):
    """Fail closed before any connector invocation."""

@dataclass(frozen=True)
class Handoff:
    request_id: str
    tenant_id: str
    action: str
    source_ids: tuple[str, ...]
    sensitivity: str
    estimated_cost_sek: float
    provenance: str
    fingerprint: str

def validate_draft(payload: dict, *, authorized_tenant: str, max_cost_sek: float = 0.0) -> Handoff:
    if not isinstance(payload, dict) or set(payload) != REQUIRED:
        raise IntegrationDenied("Unexpected or missing fields")
    if payload["contract_version"] != "pontura.jarvis.v1" or payload["project"] != "pontura":
        raise IntegrationDenied("Wrong contract or project")
    if payload["origin"] != "jarvis-omega-v2":
        raise IntegrationDenied("Unexpected origin label")
    if payload["tenant_id"] != authorized_tenant or not isinstance(authorized_tenant, str):
        raise IntegrationDenied("Wrong tenant")
    if not isinstance(payload["request_id"], str) or not SAFE_ID.fullmatch(payload["request_id"]):
        raise IntegrationDenied("Invalid request ID")
    if payload["action"] not in ACTIONS or payload["status"] != "draft":
        raise IntegrationDenied("No executable actions or approvals")
    if payload["sensitivity"] not in SENSITIVITY:
        raise IntegrationDenied("Only public/internal metadata")
    refs = payload["source_ids"]
    if not isinstance(refs, list) or len(refs) > 25 or len(refs) != len(set(map(str, refs))):
        raise IntegrationDenied("Invalid references")
    if any(not isinstance(r, str) or not SAFE_ID.fullmatch(r) for r in refs):
        raise IntegrationDenied("Invalid source ID")
    source = payload["provenance"]
    if not isinstance(source, str) or not re.fullmatch(r"github:rickyraippalinna/jarvis-omega-v2@[a-f0-9]{40}", source):
        raise IntegrationDenied("Unpinned source provenance")
    cost = payload["estimated_cost_sek"]
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost):
        raise IntegrationDenied("Invalid cost")
    if not (0 <= cost <= max_cost_sek):
        raise IntegrationDenied("Cost approval required")
    if max_cost_sek < 0 or not math.isfinite(max_cost_sek):
        raise IntegrationDenied("Invalid budget policy")
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8")).hexdigest()
    return Handoff(payload["request_id"], payload["tenant_id"], payload["action"], tuple(refs),
                   payload["sensitivity"], float(cost), source, digest)
