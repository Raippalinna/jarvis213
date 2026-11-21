"""Server-side Pontura bridge gate. No network calls or secret persistence.

Authentication is HMAC-SHA256 over canonical payload + timestamp + nonce.
Call only from a trusted backend with a server-held, tenant-scoped key.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import sqlite3
import time

from bridge_contract import IntegrationDenied, validate_draft

NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")

def canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def signature(secret: bytes, timestamp: int, nonce: str, payload: dict) -> str:
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise IntegrationDenied("Weak or absent server secret")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        raise IntegrationDenied("Invalid timestamp")
    if not isinstance(nonce, str) or not NONCE_PATTERN.fullmatch(nonce):
        raise IntegrationDenied("Invalid nonce")
    body = str(timestamp).encode() + b"." + nonce.encode() + b"." + canonical(payload)
    return hmac.new(secret, body, hashlib.sha256).hexdigest()

@dataclass(frozen=True)
class Receipt:
    request_id: str
    tenant_id: str
    fingerprint: str
    accepted_at: int
    status: str = "draft"

class SecureIngress:
    """Transactional, single-database replay guard. SQLite for tests/single node only.

    Production multi-node systems need one shared transactional database, a
    server identity layer and tenant-scoped key rotation. Not a public endpoint.
    """
    def __init__(self, conn: sqlite3.Connection, *, max_skew_seconds: int = 300):
        self.conn = conn
        self.max_skew_seconds = max_skew_seconds
        self.conn.execute("""CREATE TABLE IF NOT EXISTS pontura_handoff_receipt (
            tenant_id TEXT NOT NULL, request_id TEXT NOT NULL,
            nonce TEXT NOT NULL, fingerprint TEXT NOT NULL,
            accepted_at INTEGER NOT NULL, status TEXT NOT NULL,
            PRIMARY KEY (tenant_id, request_id), UNIQUE (tenant_id, nonce))""")
        self.conn.commit()

    def accept(self, payload: dict, *, authenticated_tenant: str, server_secret: bytes,
               timestamp: int, nonce: str, supplied_signature: str,
               now: int | None = None, max_cost_sek: float = 0.0) -> Receipt:
        if now is None:
            now = int(time.time())
        if isinstance(now, bool) or not isinstance(now, int):
            raise IntegrationDenied("Invalid clock")
        if not isinstance(supplied_signature, str) or not re.fullmatch(r"[a-f0-9]{64}", supplied_signature):
            raise IntegrationDenied("Invalid signature format")
        if abs(now - timestamp) > self.max_skew_seconds:
            raise IntegrationDenied("Expired request")
        expected = signature(server_secret, timestamp, nonce, payload)
        if not hmac.compare_digest(expected, supplied_signature):
            raise IntegrationDenied("Authentication failed")
        draft = validate_draft(payload, authorized_tenant=authenticated_tenant,
                               max_cost_sek=max_cost_sek)
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO pontura_handoff_receipt "
                    "(tenant_id, request_id, nonce, fingerprint, accepted_at, status) "
                    "VALUES (?, ?, ?, ?, ?, 'draft')",
                    (draft.tenant_id, draft.request_id, nonce, draft.fingerprint, now),
                )
        except sqlite3.IntegrityError as exc:
            raise IntegrationDenied("Replay or duplicate request") from exc
        return Receipt(draft.request_id, draft.tenant_id, draft.fingerprint, now)
