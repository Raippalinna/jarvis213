"""Credential-safe, read-only Supabase backend preflight.

Exit code 0 proves that the configured backend key can read the required
runtime tables and that autonomy is enabled. It does not prove writes or
tenant isolation.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple

from jarvis.supabase_auth import (
    SupabaseAuthError,
    backend_headers,
    classify_backend_key,
    ensure_expected_project_url,
    resolve_backend_key,
)


PROBES = {
    "autonomy": "system_config?key=eq.autonomy_enabled&select=value",
    "memory_read": "jarvis_memory?select=id&limit=1",
    "audit_read": "approval_audit_log?select=id&limit=1",
}


def run_preflight() -> Tuple[str, Dict[str, Any]]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = resolve_backend_key()
    result: Dict[str, Any] = {
        "backend_key_kind_unverified": classify_backend_key(key),
        "checks": {},
    }

    if not url or not key:
        return "not_configured", result
    try:
        url = ensure_expected_project_url(url)
        headers = backend_headers(key, content_type=None)
    except SupabaseAuthError as exc:
        return exc.code, result

    for name, path in PROBES.items():
        try:
            req = urllib.request.Request(
                f"{url}/rest/v1/{path}",
                headers=headers,
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                rows = json.loads(response.read(65537))
            if name == "autonomy":
                allowed = (
                    isinstance(rows, list)
                    and len(rows) == 1
                    and rows[0].get("value") in {True, "true"}
                )
                result["checks"][name] = "enabled" if allowed else "stopped_or_unknown"
            else:
                result["checks"][name] = "read_ok_write_untested"
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                result["checks"][name] = "unauthorized_401"
            elif exc.code == 403:
                result["checks"][name] = "forbidden_403"
            else:
                result["checks"][name] = f"http_{exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError):
            result["checks"][name] = "network_error"
        except (ValueError, TypeError, json.JSONDecodeError):
            result["checks"][name] = "invalid_response"

    checks = result["checks"]
    if checks.get("autonomy") != "enabled":
        status = (
            "autonomy_stopped_or_unknown"
            if checks.get("autonomy") == "stopped_or_unknown"
            else "backend_access_failed"
        )
    elif all(
        checks.get(name) == "read_ok_write_untested"
        for name in ("memory_read", "audit_read")
    ):
        status = "ok_read_only"
    else:
        status = "backend_access_failed"
    return status, result


def main() -> int:
    status, result = run_preflight()
    result["status"] = status
    print(json.dumps(result, sort_keys=True))
    return 0 if status == "ok_read_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
