"""ApprovalGate — kopplar godmode-autonominivåerna (L0-L3) till de riktiga
approval_* tabellerna i Supabase (skapade 2026-09-02, tidigare oanvända).

Risk-klasser (matchar autonomiladdern redan dokumenterad i
jarvis-connector-map-skillen och godmode-driftprotokollet):

  R0 — läsning/research/strategi. Ingen skrivning utanför Notion/loggar.
       Ingen approval krävs.
  R1 — reversibel intern skrivning (kodändring, ny rad i en intern tabell,
       GitHub-commit). Auto, men loggas i approval_audit_log för spårbarhet.
  R2 — extern kommunikation eller affärsdata (mejl till kund, HubSpot-deal,
       publicering, kunddata). Skapar en approval_decision + approval_request
       med status='pending' och HALTAR hela turen — ingen LLM-exekvering sker
       förrän Ricky uttryckligen godkänt raden i Supabase (eller ber
       Perplexity Computer att göra det åt honom).
  R3 — pengar, avtal, oåterkallelig handling. Samma spärr som R2, men
       risk_class='R3' och reversibility='irreversible' i beslutsloggen så
       att den syns extra tydligt.

Reglerna är DETERMINISTISK kod, inte en LLM — samma princip som redan gäller
för Frugality-agenten (se agents/frugality.py). En LLM får aldrig själv
avgöra om den får hoppa över en approval-grind.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from uuid import UUID
from typing import Any, Dict, Optional

from jarvis.supabase_auth import (
    SupabaseAuthError,
    backend_headers,
    ensure_expected_project_url,
    resolve_backend_key,
)


SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
ALLOWED_APPROVAL_TABLES = frozenset({"approval_decision", "approval_request", "approval_audit_log"})

class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward backend credentials to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None



# JARVIS Prime är idag enanvändardrift (bara Ricky). Dessa är RIKTIGA rader
# i tenant/principal (skapade 2026-09-02): tenant = Ricky Raippalinna,
# principal = en dedikerad "JARVIS Agent"-identitet (type='agent') så att
# approval-loggen tydligt visar att JARVIS, inte Ricky, begärde åtgärden.
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_PRINCIPAL_ID = "22222222-2222-2222-2222-222222222222"

R3_KEYWORDS = (
    "betala", "betalning", "faktura", "avtal", "kontrakt", "underteckna",
    "köp", "beställ", "radera permanent", "ta bort permanent",
    "skicka pengar", "överföring",
)
R2_KEYWORDS = (
    "skicka mejl", "skicka e-post", "maila", "kontakta kund", "publicera",
    "posta publikt", "skicka till kund", "svara kund", "hubspot-deal",
    "extern kommunikation", "skicka offert", "skicka faktura",
    "kunddata", "personuppgifter",
)


@dataclass
class RiskDecision:
    risk_class: str          # "R0" | "R1" | "R2" | "R3"
    requires_approval: bool
    reason: str


def classify_risk(task_text: str, intent_category: str) -> RiskDecision:
    t = (task_text or "").lower()
    if any(k in t for k in R3_KEYWORDS):
        return RiskDecision(
            "R3", True, "Nyckelord indikerar pengar, avtal eller en oåterkallelig handling"
        )
    if any(k in t for k in R2_KEYWORDS):
        return RiskDecision(
            "R2", True, "Nyckelord indikerar extern kommunikation eller affärs-/kunddata"
        )
    if intent_category == "coding":
        return RiskDecision("R1", False, "Kod-/systemändring — reversibel intern skrivning")
    return RiskDecision("R0", False, "Läsning, research eller strategisk analys")


class ApprovalGate:
    """Tunn REST-klient mot approval_decision / approval_request /
    approval_audit_log via PostgREST, samma mönster som MemoryStore.
    """

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.supabase_url = (supabase_url or os.environ.get(SUPABASE_URL_ENV, "")).rstrip("/")
        self.supabase_key = resolve_backend_key(supabase_key)
        self.tenant_id = os.environ.get("JARVIS_TENANT_ID", DEFAULT_TENANT_ID)
        self.principal_id = os.environ.get("JARVIS_PRINCIPAL_ID", DEFAULT_PRINCIPAL_ID)

    @property
    def enabled(self) -> bool:
        """Only a backend-authorized client can create or read approval records."""
        if not self.supabase_url or not self.supabase_key:
            return False
        try:
            ensure_expected_project_url(self.supabase_url)
            backend_headers(self.supabase_key)
        except SupabaseAuthError:
            return False
        return True

    @staticmethod
    def _valid_id(value: object) -> bool:
        """Require a canonical backend-issued UUID, never a model-provided ID."""
        if not isinstance(value, str):
            return False
        try:
            return str(UUID(value)) == value.lower() and len(value) == 36
        except (ValueError, AttributeError):
            return False

    def _headers(self) -> Dict[str, str]:
        ensure_expected_project_url(self.supabase_url)
        return backend_headers(self.supabase_key, prefer="return=representation")

    def _insert(self, table: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if table not in ALLOWED_APPROVAL_TABLES or not isinstance(row, dict):
            return None
        if not self.enabled:
            print(f"[ApprovalGate] insert till {table} hoppad över: enabled=False "
                  f"(url_set={bool(self.supabase_url)}, key_set={bool(self.supabase_key)})")
            return None
        try:
            req = urllib.request.Request(
                f"{self.supabase_url}/rest/v1/{table}",
                method="POST",
                data=json.dumps(row).encode("utf-8"),
                headers=self._headers(),
            )
            # urllib's default opener follows 30x responses; that can leak
            # our service-role credential across origins. Never redirect.
            opener = urllib.request.build_opener(_RejectRedirect)
            with opener.open(req, timeout=15) as r:
                resp = json.loads(r.read())
                return resp[0] if isinstance(resp, list) and resp else None
        except SupabaseAuthError as exc:
            print(f"[ApprovalGate] Konfigurationsfel vid insert till {table}: {exc.code}")
            return None
        except urllib.error.HTTPError as exc:
            print(f"[ApprovalGate] HTTPError vid insert till {table}: {exc.code}")
            return None
        except Exception as exc:
            print(f"[ApprovalGate] Oväntat fel vid insert till {table}: {type(exc).__name__}")
            return None

    def open_gate(
        self,
        task_text: str,
        risk: RiskDecision,
        session_id: str,
        est_cost_sek: float = 0.0,
    ) -> Optional[str]:
        """R2/R3: skapar decision+request-rader. Returnerar request_id (str) eller None."""
        if not self.enabled:
            return None
        decision = self._insert(
            "approval_decision",
            {
                "tenant_id": self.tenant_id,
                "title": task_text[:120],
                "description": task_text[:2000],
                # decision_type CHECK: investment|contract|hire|offer|policy|other
                "decision_type": "contract" if risk.risk_class == "R3" else "other",
                # status CHECK: draft|pending_approval|approved|rejected|cancelled|executed
                "status": "pending_approval",
                "risk_class": risk.risk_class,
                "probability": 0.5,
                "cash_required": est_cost_sek or None,
                "reversibility": "irreversible" if risk.risk_class == "R3" else "reversible",
                "owner_principal_id": self.principal_id,
            },
        )
        if not isinstance(decision, dict) or not self._valid_id(decision.get("id")):
            return None
        request = self._insert(
            "approval_request",
            {
                "decision_id": decision["id"],
                # request_type CHECK: create|update|execute|cancel
                "request_type": "execute",
                "risk_class": risk.risk_class,
                "requested_by": self.principal_id,
            },
        )
        if not isinstance(request, dict) or not self._valid_id(request.get("id")):
            return None
        audit = self._insert(
            "approval_audit_log",
            {
                "tenant_id": self.tenant_id,
                "event_type": "gate_opened",
                "actor_type": "agent",
                "decision_id": decision["id"],
                "request_id": request["id"],
                "metadata": {
                    "session_id": session_id,
                    "risk_class": risk.risk_class,
                    "reason": risk.reason,
                },
            },
        )
        if not isinstance(audit, dict) or not self._valid_id(audit.get("id")):
            # If audit write failed, never report this request as ready for review.
            return None
        return str(request["id"])

    def log_auto(self, task_text: str, risk: RiskDecision, session_id: str) -> None:
        """R0/R1: ingen approval, men en spårbar rad i audit-loggen."""
        if not self.enabled:
            return
        self._insert(
            "approval_audit_log",
            {
                "tenant_id": self.tenant_id,
                "event_type": "auto_executed",
                "actor_type": "agent",
                "metadata": {
                    "session_id": session_id,
                    "risk_class": risk.risk_class,
                    "reason": risk.reason,
                    "task_preview": (task_text or "")[:300],
                },
            },
        )
