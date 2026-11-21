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
import hashlib
import math
import re
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
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
    """Reject redirects before any backend credential can leave the trusted origin."""

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
        if not self.supabase_url or not self.supabase_key:
            return False
        try:
            ensure_expected_project_url(self.supabase_url)
            backend_headers(self.supabase_key)
        except SupabaseAuthError:
            return False
        return True

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
            # Never send server credentials to a 30x redirect target.
            with urllib.request.build_opener(_RejectRedirect).open(req, timeout=15) as r:
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

    def _rpc_open(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Single privileged RPC. No external redirects, no partial-row writes."""
        if not self.enabled:
            return None

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        try:
            request = urllib.request.Request(
                f"{self.supabase_url}/rest/v1/rpc/jarvis_approval_open",
                method="POST",
                data=json.dumps(payload, allow_nan=False).encode("utf-8"),
                headers=self._headers(),
            )
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(request, timeout=15) as response:
                data = json.loads(response.read())
            return data if isinstance(data, dict) else None
        except (SupabaseAuthError, urllib.error.URLError, ValueError, TypeError, OSError):
            return None

    def open_gate(self, task_text: str, risk: RiskDecision, session_id: str,
                  est_cost_sek: float = 0.0) -> Optional[str]:
        """One atomic, action-bound R2/R3 request. Fail closed until RPC deployed."""
        if not self.enabled or risk.risk_class not in ("R2", "R3"):
            return None
        if not risk.requires_approval or not isinstance(task_text, str) or not 4 <= len(task_text.strip()) <= 2000:
            return None
        if not isinstance(session_id, str) or not 1 <= len(session_id) <= 128:
            return None
        if not isinstance(est_cost_sek, (int, float)) or not math.isfinite(est_cost_sek) or not 0 <= est_cost_sek <= 200:
            return None
        canonical = json.dumps(
            {"tenant_id": self.tenant_id, "agent_principal_id": self.principal_id,
             "task": task_text, "session_id": session_id, "risk_class": risk.risk_class},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        result = self._rpc_open({
            "p_tenant_id": self.tenant_id, "p_agent_principal_id": self.principal_id,
            "p_title": task_text[:120], "p_description": task_text,
            "p_risk": risk.risk_class, "p_action_sha256": digest,
            "p_session_id": session_id, "p_est_cost": est_cost_sek,
        })
        request_id = result.get("request_id") if result else None
        if not isinstance(request_id, str) or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            request_id, re.IGNORECASE,
        ) is None:
            return None
        return request_id


    def _rpc_check(self, payload: Dict[str, Any]) -> bool:
        """Read back an exact approved action from a service-role-only RPC."""
        if not self.enabled:
            return False

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        try:
            request = urllib.request.Request(
                f"{self.supabase_url}/rest/v1/rpc/jarvis_approval_check",
                method="POST",
                data=json.dumps(payload, allow_nan=False).encode("utf-8"),
                headers=self._headers(),
            )
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
                return json.loads(response.read()) is True
        except (SupabaseAuthError, urllib.error.URLError, ValueError, TypeError, OSError):
            return False

    def is_approved(self, request_id: str, task_text: str,
                    risk: RiskDecision, session_id: str) -> bool:
        """Never trust approval ID alone; compare the exact persisted task digest."""
        if not self.enabled or risk.risk_class not in ("R2", "R3"):
            return False
        if not isinstance(task_text, str) or not 4 <= len(task_text.strip()) <= 2000:
            return False
        if not isinstance(session_id, str) or not 1 <= len(session_id) <= 128:
            return False
        if not isinstance(request_id, str) or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            request_id, re.IGNORECASE,
        ) is None:
            return False
        canonical = json.dumps(
            {"tenant_id": self.tenant_id, "agent_principal_id": self.principal_id,
             "task": task_text, "session_id": session_id, "risk_class": risk.risk_class},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self._rpc_check({
            "p_tenant_id": self.tenant_id,
            "p_request_id": request_id,
            "p_action_sha256": digest,
        })

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
