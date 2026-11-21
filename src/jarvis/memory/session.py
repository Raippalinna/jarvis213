"""Autentiserad minnessession; medlemskap avgörs separat av RLS.

Ingen aktivering i supervisor ingår. Tokens får inte serialiseras.
"""
from __future__ import annotations
import json
import urllib.error
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import UUID

ORIGIN = "https://fzmnqvmfilqizzftphbt.supabase.co"
MAX_RESPONSE = 128_000

class MemorySessionError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def _uuid(value):
    if not isinstance(value, str):
        raise MemorySessionError("identity_invalid")
    try:
        result = UUID(value)
    except ValueError:
        raise MemorySessionError("identity_invalid") from None
    if result.int == 0:
        raise MemorySessionError("identity_invalid")
    return str(result)

@dataclass(frozen=True)
class AuthenticatedMemorySession:
    tenant_id: str
    user_id: str
    publishable_key: str = field(repr=False)
    access_token: str = field(repr=False)

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def verify_session(*, access_token, requested_tenant_id, publishable_key):
    """Verifiera användaren via Auth. Tenant-val är inte medlemskapsbevis."""
    tenant_id = _uuid(requested_tenant_id)
    if (not isinstance(access_token, str) or not access_token
            or len(access_token) > 16384
            or any(c.isspace() for c in access_token)):
        raise MemorySessionError("token_invalid")
    if (not isinstance(publishable_key, str)
            or not publishable_key.startswith("sb_publishable_")
            or len(publishable_key) > 1024
            or any(c.isspace() for c in publishable_key)):
        raise MemorySessionError("publishable_key_required")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect())
    request = urllib.request.Request(
        ORIGIN + "/auth/v1/user", method="GET",
        headers={"apikey": publishable_key,
                 "Authorization": "Bearer " + access_token,
                 "Accept": "application/json"})
    try:
        with opener.open(request, timeout=10) as response:
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise MemorySessionError(
            "authentication_failed" if status in (401, 403)
            else "authentication_unavailable") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise MemorySessionError("authentication_unavailable") from None
    if len(raw) > MAX_RESPONSE:
        raise MemorySessionError("auth_response_invalid")
    try:
        user = json.loads(raw)
    except (ValueError, UnicodeError):
        raise MemorySessionError("auth_response_invalid") from None
    if not isinstance(user, dict):
        raise MemorySessionError("auth_response_invalid")
    if user.get("role") != "authenticated":
        raise MemorySessionError("user_role_not_supported")
    user_id = _uuid(user.get("id"))
    return AuthenticatedMemorySession(
        tenant_id, user_id, publishable_key, access_token)

_current = ContextVar("jarvis_memory_session", default=None)

def current_session():
    session = _current.get()
    if session is None:
        raise MemorySessionError("session_required")
    return session

@contextmanager
def bind_session(session):
    """Endast betrodd serverkod får binda sessioner. Skapa inga bakgrundsjobb."""
    if not isinstance(session, AuthenticatedMemorySession):
        raise MemorySessionError("session_invalid")
    token = _current.set(session)
    try:
        yield session
    finally:
        _current.reset(token)
