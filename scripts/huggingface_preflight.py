#!/usr/bin/env python3
"""Read-only Hugging Face identity and public-catalog checks; no inference."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

IDENTITY_URL = "https://huggingface.co/api/whoami-v2"
CATALOG_URL = "https://router.huggingface.co/v1/models"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class PreflightFailure(RuntimeError):
    """Only locally defined, non-sensitive reason codes may be reported."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the identity credential to a redirect target.
        return None


def request_json(url: str, token: str = "") -> object:
    if url not in {IDENTITY_URL, CATALOG_URL}:
        raise PreflightFailure("endpoint_not_allowed")
    if token and url != IDENTITY_URL:
        raise PreflightFailure("credential_destination_not_allowed")
    headers = {"Accept": "application/json", "User-Agent": "jarvis-hf-preflight"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=20) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise PreflightFailure("response_too_large")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise PreflightFailure("invalid_json") from None


def verify_connection(token: str, expected_user: str) -> dict:
    if not token or any(character.isspace() for character in token):
        raise PreflightFailure("credential_missing_or_invalid")
    if not expected_user or not expected_user.isascii():
        raise PreflightFailure("expected_account_missing_or_invalid")
    identity = request_json(IDENTITY_URL, token)
    if not isinstance(identity, dict) or identity.get("name") != expected_user:
        raise PreflightFailure("account_mismatch_or_invalid_response")

    # This endpoint is public. A successful catalog read is NOT an inference
    # permission, credit-balance, billing, or successful-completion test.
    catalog = request_json(CATALOG_URL)
    rows = catalog.get("data") if isinstance(catalog, dict) else None
    if not isinstance(rows, list) or not rows:
        raise PreflightFailure("empty_or_invalid_model_catalog")
    ids = [row.get("id") if isinstance(row, dict) else None for row in rows]
    if any(not isinstance(model_id, str) or not model_id.strip() for model_id in ids):
        raise PreflightFailure("invalid_model_id")
    if len(set(ids)) != len(ids):
        raise PreflightFailure("duplicate_model_id")
    return {
        "status": "identity_and_catalog_verified",
        "account": expected_user,
        "model_count": len(ids),
        "catalog_is_public": True,
        "completion_requests": 0,
        "inference_tested": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    try:
        report = verify_connection(
            os.environ.get("HF_TOKEN", "").strip(),
            os.environ.get("HF_EXPECTED_USERNAME", "").strip(),
        )
    except PreflightFailure as exc:
        report = {"status": "preflight_failed", "reason": str(exc)}
        code = 1
    except urllib.error.HTTPError as exc:
        # Do not print response bodies, request headers, URLs, or exception text.
        report = {"status": "http_error", "http_status": exc.code}
        exc.close()
        code = 1
    except (urllib.error.URLError, TimeoutError, OSError):
        report = {"status": "transport_error"}
        code = 1
    except KeyboardInterrupt:
        report = {"status": "cancelled"}
        code = 130
    except Exception:
        report = {"status": "unexpected_preflight_error"}
        code = 1
    else:
        code = 0
    print(json.dumps(report, ensure_ascii=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
