"""Fail-closed kill switch, re-read immediately before each external side effect."""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str


class SafetyStop(RuntimeError):
    def __init__(self, action: str, reason: str):
        self.action = action
        self.reason = reason
        super().__init__(f"{action}: {reason}")


def check_autonomy(*, supabase_url: str = "", supabase_key: str = "") -> GuardDecision:
    if any(os.environ.get(k, "").lower() in {"1", "true", "yes"}
           for k in ("DRY_RUN", "JARVIS_DRY_RUN")):
        return GuardDecision(False, "dry_run")
    url = (supabase_url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url.startswith("https://") or not key:
        return GuardDecision(False, "switch_credentials_missing")
    request = urllib.request.Request(
        f"{url}/rest/v1/system_config?key=eq.autonomy_enabled&select=value&limit=2",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            rows = json.loads(response.read())
        # The observed production contract is one row with a TEXT value "true".
        # Do not accept truthy strings, duplicate rows, or stale cached permission.
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            return GuardDecision(False, "switch_invalid")
        if rows[0].get("value") != "true":
            return GuardDecision(False, "switch_disabled")
        return GuardDecision(True, "switch_enabled")
    except Exception:
        return GuardDecision(False, "switch_unavailable")


def require_autonomy(action: str, **credentials) -> None:
    decision = check_autonomy(**credentials)
    if not decision.allowed:
        raise SafetyStop(action, decision.reason)
