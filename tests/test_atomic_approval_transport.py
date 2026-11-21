"""Atomic Approval Center transport hardening: no redirects or arbitrary tables.

All tests run offline with synthetic credentials; never access live Supabase.
"""
from __future__ import annotations

from urllib.request import Request
from unittest.mock import patch

from jarvis.approval.gate import ApprovalGate, _RejectRedirect

BASE = "https://fzmnqvmfilqizzftphbt.supabase.co"
KEY = "sb_secret_approval_synthetic_only"


def gate(*, url=BASE, key=KEY):
    return ApprovalGate(supabase_url=url, supabase_key=key)


def test_only_pinned_https_origin_and_backend_credential_enable_gate():
    assert gate().enabled is True
    for url in ["http://fzmnqvmfilqizzftphbt.supabase.co",
                "https://attacker.invalid", BASE + ".attacker.invalid",
                "https://fzmnqvmfilqizzftphbt.supabase.co@attacker.invalid"]:
        assert gate(url=url).enabled is False
    for key in ["", "sb_publishable_synthetic", "invalid"]:
        assert gate(key=key).enabled is False


def test_audit_writer_rejects_unexpected_table_before_network():
    for table in ["approval_decision?status=approved", "jarvis_memory",
                  "system_config", "../approval_request", ""]:
        with patch("urllib.request.build_opener") as opener:
            assert gate()._insert(table, {"status": "approved"}) is None
            opener.assert_not_called()
    with patch("urllib.request.build_opener") as opener:
        assert gate()._insert("approval_audit_log", ["invalid payload"]) is None
        opener.assert_not_called()


def test_redirect_handler_rejects_cross_origin_redirect():
    req = Request(BASE + "/rest/v1/approval_audit_log", method="POST", data=b"{}",
                  headers={"apikey": KEY})
    assert _RejectRedirect().redirect_request(
        req, None, 307, "Redirect",
        {"Location": "https://attacker.invalid/collect"},
        "https://attacker.invalid/collect",
    ) is None


def test_audit_write_installs_strict_redirect_handler():
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return b'[{"id":"11111111-1111-4111-8111-111111111111"}]'

    class FakeOpener:
        def open(self, request, timeout):
            assert request.get_method() == "POST"
            assert request.full_url == BASE + "/rest/v1/approval_audit_log"
            assert timeout == 15
            return FakeResponse()

    with patch("urllib.request.build_opener") as opener:
        opener.side_effect = lambda *handlers: (
            FakeOpener() if _RejectRedirect in handlers
            else (_ for _ in ()).throw(AssertionError("Missing deny-redirect"))
        )
        result = gate()._insert("approval_audit_log", {"event_type": "test"})
        assert result == {"id": "11111111-1111-4111-8111-111111111111"}
        opener.assert_called_once()
