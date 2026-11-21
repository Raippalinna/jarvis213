"""Offline safety tests for the backend-only JARVIS Approval Center.

Never connect to the real database, use a real credential or persist sample
approval rows. This suite checks fail-closed behavior and evidence handling.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.approval.gate import ApprovalGate, RiskDecision, classify_risk

PROJECT = "https://fzmnqvmfilqizzftphbt.supabase.co"
KEY = "sb_secret_synthetic_test_only"  # Mock string, not an actual credential.
DECISION = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
AUDIT = "33333333-3333-4333-8333-333333333333"


def gate(key=KEY, url=PROJECT):
    return ApprovalGate(supabase_url=url, supabase_key=key)


def _jwt(role):
    body = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"header.{body}.signature"


@pytest.mark.parametrize("bad_key", ["", "sb_publishable_test", _jwt("anon"), _jwt("authenticated"), "arbitrary"])
def test_public_or_invalid_key_fails_closed_without_network(bad_key):
    g = gate(key=bad_key)
    assert g.enabled is False
    with patch("urllib.request.urlopen") as urlopen:
        assert g._insert("approval_decision", {"status": "approved"}) is None
        urlopen.assert_not_called()


@pytest.mark.parametrize("url", [
    "http://fzmnqvmfilqizzftphbt.supabase.co",
    "https://evil.example.invalid",
    "https://fzmnqvmfilqizzftphbt.supabase.co.evil.invalid",
    "https://fzmnqvmfilqizzftphbt.supabase.co@evil.invalid",
    "https://fzmnqvmfilqizzftphbt.supabase.co/evil",
])
def test_bad_destination_rejected_before_network(url):
    g = gate(url=url)
    assert g.enabled is False
    with patch("urllib.request.urlopen") as urlopen:
        assert g._insert("approval_audit_log", {"event_type": "test"}) is None
        urlopen.assert_not_called()


@pytest.mark.parametrize("table", ["jarvis_memory", "system_config", "approval_decision?status=approved", "../approval_request", ""])
def test_approval_writer_cannot_target_another_table(table):
    with patch("urllib.request.urlopen") as urlopen:
        assert gate()._insert(table, {"status": "approved"}) is None
        urlopen.assert_not_called()


def test_invalid_payload_type_rejected():
    with patch("urllib.request.urlopen") as urlopen:
        assert gate()._insert("approval_decision", ["unexpected"]) is None
        urlopen.assert_not_called()


def test_valid_review_request_needs_all_three_backend_receipts(monkeypatch):
    g = gate()
    order = []
    def stub(table, row):
        order.append(table)
        assert row.get("status") != "approved"  # Agent never grants approval.
        return {
            "approval_decision": {"id": DECISION},
            "approval_request": {"id": REQUEST},
            "approval_audit_log": {"id": AUDIT},
        }[table]
    monkeypatch.setattr(g, "_insert", stub)
    response = g.open_gate("publicera sida", RiskDecision("R2", True, "review"), "offline-session")
    assert response == REQUEST
    assert order == ["approval_decision", "approval_request", "approval_audit_log"]


@pytest.mark.parametrize("bad_record", [None, [], {}, {"id": "not-a-uuid"}, {"id": "11111111-1111-4111-8111-111111111111?leak"}])
def test_invalid_decision_receipt_prevents_request(monkeypatch, bad_record):
    g = gate()
    calls = []
    def stub(table, row):
        calls.append(table)
        return bad_record
    monkeypatch.setattr(g, "_insert", stub)
    assert g.open_gate("skicka offert", RiskDecision("R2", True, "review"), "offline") is None
    assert calls == ["approval_decision"]


def test_request_failure_does_not_emit_success_or_audit(monkeypatch):
    g = gate()
    calls = []
    def stub(table, row):
        calls.append(table)
        return {"approval_decision": {"id": DECISION}, "approval_request": None}[table]
    monkeypatch.setattr(g, "_insert", stub)
    assert g.open_gate("skicka mejl", RiskDecision("R2", True, "review"), "offline") is None
    assert calls == ["approval_decision", "approval_request"]


def test_audit_failure_does_not_report_request_as_ready(monkeypatch):
    g = gate()
    calls = []
    def stub(table, row):
        calls.append(table)
        return {
            "approval_decision": {"id": DECISION},
            "approval_request": {"id": REQUEST},
            "approval_audit_log": None,
        }[table]
    monkeypatch.setattr(g, "_insert", stub)
    assert g.open_gate("sign contract", RiskDecision("R3", True, "review"), "offline") is None
    assert calls == ["approval_decision", "approval_request", "approval_audit_log"]


def test_audit_failure_cannot_log_or_expose_secrets(monkeypatch, capsys):
    g = gate()
    def mock_error(_request, timeout):
        raise RuntimeError("INTERNAL_TOKEN_SHOULD_NOT_BE_IN_LOGS")
    monkeypatch.setattr("urllib.request.urlopen", mock_error)
    assert g.log_auto("test", RiskDecision("R1", False, "log"), "session") is None
    assert "INTERNAL_TOKEN_SHOULD_NOT_BE_IN_LOGS" not in capsys.readouterr().out


def test_approval_risk_class_remains_deterministic():
    assert classify_risk("skicka faktura", "coding").risk_class == "R3"
    assert classify_risk("skicka mejl", "coding").requires_approval is True
    assert classify_risk("fixa python", "coding").risk_class == "R1"


def test_transport_installs_deny_redirect_handler(monkeypatch):
    from jarvis.approval.gate import _RejectRedirect
    seen = []

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return b'[{"id":"11111111-1111-4111-8111-111111111111"}]'

    class FakeOpener:
        def open(self, req, timeout):
            assert timeout == 15
            seen.append(req)
            return FakeResponse()

    def fake_build_opener(*handlers):
        assert any(h is _RejectRedirect for h in handlers)
        return FakeOpener()

    monkeypatch.setattr("urllib.request.build_opener", fake_build_opener)
    result = gate()._insert("approval_decision", {"status": "pending_approval"})
    assert result == {"id": DECISION}
    assert len(seen) == 1


def test_redirect_target_never_receives_backend_request():
    from jarvis.approval.gate import _RejectRedirect
    from urllib.request import Request

    req = Request(
        f"{PROJECT}/rest/v1/approval_decision",
        method="POST",
        data=b"{}",
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"},
    )
    assert _RejectRedirect().redirect_request(
        req, None, 307, "redirect", {"Location": "https://evil.invalid/capture"},
        "https://evil.invalid/capture",
    ) is None
