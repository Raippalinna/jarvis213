"""Unit tests for Supabase backend authentication; synthetic keys only."""
import base64
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.memory.store import MemoryStore
from jarvis.approval.gate import ApprovalGate
from unittest.mock import patch
from jarvis.supabase_auth import (
    SupabaseAuthError,
    backend_headers,
    classify_backend_key,
    ensure_expected_project_url,
    resolve_backend_key,
)


def _jwt(role):
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def test_modern_secret_uses_apikey_without_bearer():
    key = "sb_" + "secret_synthetic_test_only"
    headers = backend_headers(key, prefer="return=representation")
    assert headers["apikey"] == key
    assert "Authorization" not in headers
    assert headers["Prefer"] == "return=representation"


def test_legacy_service_role_uses_bearer():
    key = _jwt("service_role")
    headers = backend_headers(key)
    assert headers["apikey"] == key
    assert headers["Authorization"] == f"Bearer {key}"


@pytest.mark.parametrize("key", ["sb_" + "publishable_test", _jwt("anon"), _jwt("authenticated")])
def test_public_keys_are_rejected(key):
    with pytest.raises(SupabaseAuthError, match="public_key_rejected"):
        backend_headers(key)


def test_unknown_key_is_rejected():
    with pytest.raises(SupabaseAuthError, match="unknown_key_type"):
        backend_headers("not-a-backend-key")


def test_modern_secret_takes_precedence_over_legacy():
    env = {
        "SUPABASE_SECRET_KEY": "sb_" + "secret_modern",
        "SUPABASE_SERVICE_ROLE_KEY": _jwt("service_role"),
    }
    assert resolve_backend_key(environ=env) == env["SUPABASE_SECRET_KEY"]


def test_expected_project_url_is_exact():
    assert ensure_expected_project_url(
        "https://fzmnqvmfilqizzftphbt.supabase.co/"
    ) == "https://fzmnqvmfilqizzftphbt.supabase.co"
    with pytest.raises(SupabaseAuthError, match="unexpected_project_url"):
        ensure_expected_project_url("https://example.supabase.co")


@pytest.mark.parametrize("client_class", [MemoryStore, ApprovalGate])
def test_backend_clients_reject_unexpected_host(client_class):
    client = client_class(
        supabase_url="https://example.invalid",
        supabase_key="sb_" + "secret_synthetic_test_only",
    )
    with pytest.raises(SupabaseAuthError, match="unexpected_project_url"):
        client._headers()


def test_memory_read_and_approval_write_stop_before_network_on_bad_host():
    key = "sb_" + "secret_synthetic_test_only"
    memory = MemoryStore(supabase_url="https://example.invalid", supabase_key=key)
    approval = ApprovalGate(supabase_url="https://example.invalid", supabase_key=key)
    with patch("urllib.request.urlopen") as network:
        assert memory._fulltext_only("test", 5, None, None) == []
        assert approval._insert("approval_audit_log", {"event_type": "test"}) is None
        network.assert_not_called()
