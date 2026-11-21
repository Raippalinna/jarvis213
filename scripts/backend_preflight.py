"""Read-only backend checks. Prints status only, never credentials or row data."""
import base64
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


def key_kind(key):
    if key.startswith("sb_secret_"):
        return "secret_key"
    if key.startswith("sb_publishable_"):
        return "publishable"
    try:
        payload = key.split(".")[1]
        role = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("role")
        return role if role in ("anon", "authenticated", "service_role") else "unknown"
    except Exception:
        return "unknown"


def main():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    result = {"comet_secret_present": bool(os.environ.get("COMET_API_KEY")),
              "backend_key_kind_unverified": key_kind(key), "checks": {}}
    # Fixed approved project: do not send this secret to an arbitrary URL.
    if urlparse(url).scheme != "https" or urlparse(url).netloc != "fzmnqvmfilqizzftphbt.supabase.co":
        result["configuration"] = "unexpected_project_url"
        print(json.dumps(result))
        return 1
    paths = {
        "autonomy": "system_config?key=eq.autonomy_enabled&select=value",
        "memory_read": "jarvis_memory?select=id&limit=1",
        "audit_read": "approval_audit_log?select=id&limit=1",
    }
    headers = {"apikey": key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    for name, path in paths.items():
        try:
            req = urllib.request.Request(url + "/rest/v1/" + path, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                rows = json.loads(response.read())
            if name == "autonomy":
                allowed = len(rows) == 1 and (rows[0].get("value") is True or rows[0].get("value") == "true")
                result["checks"][name] = "enabled" if allowed else "stopped_or_unknown"
            else:
                result["checks"][name] = "read_ok_write_untested"
        except urllib.error.HTTPError as exc:
            result["checks"][name] = f"http_{exc.code}"
        except Exception as exc:
            result["checks"][name] = type(exc).__name__
    print(json.dumps(result, sort_keys=True))
    passed = (result["backend_key_kind_unverified"] in ("service_role", "secret_key")
              and result["checks"].get("autonomy") == "enabled"
              and all(result["checks"].get(k) == "read_ok_write_untested" for k in ("memory_read", "audit_read")))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
