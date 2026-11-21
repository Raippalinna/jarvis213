"""Supabase backend authentication without leaking or misusing credentials."""
from __future__ import annotations

import base64
import json
import os
from typing import Dict, Mapping, Optional
from urllib.parse import urlparse


EXPECTED_SUPABASE_URL = "https://fzmnqvmfilqizzftphbt.supabase.co"
SECRET_KEY_ENV = "SUPABASE_SECRET_KEY"
LEGACY_SERVICE_ROLE_ENV = "SUPABASE_SERVICE_ROLE_KEY"


class SupabaseAuthError(ValueError):
    """Safe configuration error identified by a non-sensitive code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def legacy_jwt_role(key: str) -> Optional[str]:
    """Return a legacy JWT role as a hint, never as authorization proof."""
    parts = (key or "").split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    role = claims.get("role") if isinstance(claims, dict) else None
    return role if isinstance(role, str) else None


def classify_backend_key(key: str) -> str:
    """Classify without returning or logging any key material."""
    value = (key or "").strip()
    if value.startswith("sb_secret_"):
        return "secret_key"
    if value.startswith("sb_publishable_"):
        return "public_key"
    role = legacy_jwt_role(value)
    if role == "service_role":
        return "legacy_service_role"
    if role in {"anon", "authenticated"}:
        return "public_key"
    return "unknown_key_type"


def resolve_backend_key(
    explicit_key: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Prefer the modern secret key; keep the legacy server JWT as fallback."""
    if explicit_key is not None:
        return explicit_key.strip()
    source = os.environ if environ is None else environ
    return (
        source.get(SECRET_KEY_ENV, "").strip()
        or source.get(LEGACY_SERVICE_ROLE_ENV, "").strip()
    )


def backend_headers(
    key: str,
    *,
    content_type: Optional[str] = "application/json",
    prefer: Optional[str] = None,
) -> Dict[str, str]:
    """Build PostgREST headers for a backend-only key."""
    kind = classify_backend_key(key)
    if kind == "public_key":
        raise SupabaseAuthError("public_key_rejected")
    if kind == "unknown_key_type":
        raise SupabaseAuthError("unknown_key_type")

    headers = {"apikey": key}
    if kind == "legacy_service_role":
        headers["Authorization"] = f"Bearer {key}"
    if content_type:
        headers["Content-Type"] = content_type
    if prefer:
        headers["Prefer"] = prefer
    return headers


def ensure_expected_project_url(url: str) -> str:
    """Fail closed before a backend key can be sent to another host."""
    normalized = (url or "").rstrip("/")
    parsed = urlparse(normalized)
    expected = urlparse(EXPECTED_SUPABASE_URL)
    if (
        parsed.scheme != "https"
        or parsed.netloc != expected.netloc
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise SupabaseAuthError("unexpected_project_url")
    return normalized
