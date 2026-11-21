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
       med status='pending_approval' och HALTAR hela turen.
       Detta är en begäran om granskning, inte en exekveringsbehörighet.
  R3 — nyckelord om pengar, avtal eller oåterkallelig handling. Samma spärr
       som R2; reversibilitet kan inte fastställas av denna klassificering.

Nyckelordsreglerna är en ofullständig klassificeringsheuristik, inte en
säkerhetsgräns för verktyg. Ingen godkänd återupptagning implementeras här.
"""
from __future__ import annotations

import json
import hashlib
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID
from ..safety import guard
from ..safety.secrets import redact


SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"

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
        self.supabase_key = supabase_key or os.environ.get(SUPABASE_KEY_ENV, "")
        self.tenant_id = os.environ.get("JARVIS_TENANT_ID", DEFAULT_TENANT_ID)
        self.principal_id = os.environ.get("JARVIS_PRINCIPAL_ID", DEFAULT_PRINCIPAL_ID)

    @property
    def enabled(self) -> bool:
        return bool(self.supabase_url.startswith("https://") and self.supabase_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _insert(self, table: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            print(f"[ApprovalGate] insert till {table} hoppad över: enabled=False "
                  f"(url_set={bool(self.supabase_url)}, key_set={bool(self.supabase_key)})")
            return None
        req = urllib.request.Request(
            f"{self.supabase_url}/rest/v1/{table}",
            method="POST",
            data=json.dumps(row).encode("utf-8"),
            headers=self._headers(),
        )
        try:
            guard.require_autonomy("approval_write", supabase_url=self.supabase_url,
                                   supabase_key=self.supabase_key)
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
                if not isinstance(resp, list) or len(resp) != 1 or not isinstance(resp[0], dict):
                    return None
                UUID(str(resp[0].get("id", "")))
                return resp[0]
        except urllib.error.HTTPError as e:
            print(f"[ApprovalGate] HTTPError vid insert till {table}: {e.code}")
            return None
        except Exception as exc:
            print(f"[ApprovalGate] Insert stoppad för {table}: {type(exc).__name__}")
            return None

    def open_gate(
        self,
        task_text: str,
        risk: RiskDecision,
        session_id: str,
        est_cost_sek: float = 0.0,
    ) -> Optional[str]:
        """En atomisk serveroperation, aldrig fallback till tre separata INSERT.

        Samma tenant/aktör/session/innehåll ger samma ännu väntande kvitto.
        Servermigreringen måste vara installerad separat före driftsättning.
        """
        if (not self.enabled or not risk.requires_approval
                or risk.risk_class not in {"R2", "R3"}
                or not task_text.strip() or not session_id.strip()):
            return None
        task_text = redact(task_text)
        reason = redact(risk.reason)
        # Reject oversize inputs instead of silently changing the review content.
        if len(task_text) > 2000 or len(session_id) > 128 or not reason.strip() or len(reason) > 300:
            return None
        payload = {
            "p_tenant": self.tenant_id, "p_actor": self.principal_id,
            "p_session": session_id, "p_task": task_text,
            "p_risk": risk.risk_class, "p_reason": reason,
        }
        request = urllib.request.Request(
            f"{self.supabase_url}/rest/v1/rpc/jarvis_open_review_v1",
            method="POST", data=json.dumps(payload).encode("utf-8"), headers=self._headers(),
        )
        try:
            guard.require_autonomy("approval_write", supabase_url=self.supabase_url,
                                   supabase_key=self.supabase_key)
            with urllib.request.urlopen(request, timeout=15) as response:
                receipt = json.loads(response.read())
            if (not isinstance(receipt, dict)
                    or receipt.get("state") != "pending_approval"
                    or receipt.get("scope") != "review_only"
                    or receipt.get("execution_authorized") is not False):
                return None
            for field in ("decision_id", "request_id", "audit_id"):
                UUID(str(receipt.get(field, "")))
            expires = datetime.fromisoformat(receipt["expires_at"].replace("Z", "+00:00"))
            if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
                return None
            return str(receipt["request_id"])
        except urllib.error.HTTPError as exc:
            print(f"[ApprovalGate] Review RPC HTTP-status: {exc.code}")
            return None
        except Exception as exc:
            print(f"[ApprovalGate] Review RPC stoppad: {type(exc).__name__}")
            return None

    def log_auto(self, task_text: str, risk: RiskDecision, session_id: str) -> None:
        """R0/R1: ingen approval, men en spårbar rad i audit-loggen."""
        if not self.enabled:
            return
        self._insert(
            "approval_audit_log",
            {
                "tenant_id": self.tenant_id,
                "event_type": "auto_classified",
                "actor_type": "agent",
                "actor_principal_id": self.principal_id,
                "metadata": {
                    "session_id": session_id,
                    "risk_class": risk.risk_class,
                    "reason": risk.reason,
                    "task_sha256": hashlib.sha256((task_text or "").encode()).hexdigest(),
                    "task_length": len(task_text or ""),
                },
            },
        )
