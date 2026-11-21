"""Offline regression of new atomic, action-bound Approval Center RPC."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.approval.gate import ApprovalGate, classify_risk

URL = "https://fzmnqvmfilqizzftphbt.supabase.co"
KEY = "sb_secret_synthetic_approval_test"
REQUEST_ID = "16dd4ea1-891a-47a2-9aa5-7d83be88bbd2"


def gate():
    return ApprovalGate(supabase_url=URL, supabase_key=KEY)


def test_sensitive_task_opens_one_atomic_rpc_and_canonical_hash():
    instance = gate()
    risk = classify_risk("skicka mejl till kund", "unknown")
    assert risk.risk_class == "R2"
    with patch.object(instance, "_rpc_open", return_value={"request_id": REQUEST_ID}) as rpc:
        assert instance.open_gate("skicka mejl till kund", risk, "run-001") == REQUEST_ID
    rpc.assert_called_once()
    body = rpc.call_args[0][0]
    assert body["p_action_sha256"].isascii() and len(body["p_action_sha256"]) == 64
    assert body["p_description"] == "skicka mejl till kund"
    assert body["p_session_id"] == "run-001"
    with patch.object(instance, "_rpc_open", return_value={"request_id": REQUEST_ID}) as again:
        instance.open_gate("skicka mejl till kund", risk, "run-002")
        assert again.call_args[0][0]["p_action_sha256"] != body["p_action_sha256"]


def test_rpc_failure_and_unbound_result_fail_closed():
    instance = gate()
    risk = classify_risk("skriv ett avtal", "unknown")
    assert risk.risk_class == "R3"
    for result in (None, {}, {"request_id": "fake"}, {"request_id": 1}):
        with patch.object(instance, "_rpc_open", return_value=result):
            assert instance.open_gate("skriv ett avtal", risk, "run-001") is None


def test_input_validation_runs_before_network():
    instance = gate()
    risk = classify_risk("skicka mejl", "unknown")
    for task, session, cost in [
        ("skicka mejl", "", 0), ("skicka mejl", "x" * 129, 0),
        ("skicka mejl" + "X" * 2100, "run-123", 0),
        ("skicka mejl", "run-123", -1),
        ("skicka mejl", "run-123", float("inf")),
        ("skicka mejl", "run-123", float("nan")),
    ]:
        with patch.object(instance, "_rpc_open") as rpc:
            assert instance.open_gate(task, risk, session, cost) is None
            rpc.assert_not_called()


def test_unprivileged_risk_class_never_opens_request():
    instance = gate()
    with patch.object(instance, "_rpc_open") as rpc:
        assert instance.open_gate("write code", classify_risk("write code", "coding"), "run-001") is None
        rpc.assert_not_called()


def test_pinned_url_prevents_rpc_call_to_wrong_project():
    instance = ApprovalGate(supabase_url="https://wrong.supabase.co", supabase_key=KEY)
    with patch("urllib.request.build_opener") as opener:
        assert instance._rpc_open({"p_risk": "R2"}) is None
        opener.assert_not_called()


def test_stage_sql_contains_revokes_and_atomic_rpcs():
    root = Path(__file__).resolve().parents[1]
    stage = (root / "docs/security/sql/01_approval_backend_staging.sql").read_text()
    cutover = (root / "docs/security/sql/02_approval_grants_cutover.sql").read_text()
    for name in ("jarvis_approval_open", "jarvis_approval_decide"):
        assert "FUNCTION public." + name in stage
        assert "REVOKE ALL ON FUNCTION public." + name in stage
    assert "FOR UPDATE OF r, d" in stage
    assert "SECURITY DEFINER SET search_path = ''" in stage
    assert "DROP POLICY IF EXISTS jarvis_anon_tenant_update" in cutover
    assert "No independently verified Approval Center administrator" in cutover


def test_approval_readback_requires_exact_action_and_authenticated_backend():
    instance = gate()
    risk = classify_risk("skicka mejl till kund", "unknown")
    with patch.object(instance, "_rpc_open", return_value={"request_id": REQUEST_ID}) as opened:
        assert instance.open_gate("skicka mejl till kund", risk, "run-001") == REQUEST_ID
        expected = opened.call_args[0][0]["p_action_sha256"]
    with patch.object(instance, "_rpc_check", side_effect=lambda payload: payload["p_action_sha256"] == expected) as check:
        assert instance.is_approved(REQUEST_ID, "skicka mejl till kund", risk, "run-001") is True
        assert check.call_args[0][0]["p_action_sha256"] == expected
        check.reset_mock()
        assert instance.is_approved(REQUEST_ID, "skicka mejl till annan kund", risk, "run-001") is False
        assert check.call_args[0][0]["p_action_sha256"] != expected
    # Backend return false is the only trustworthy denial, never infer from IDs.
    with patch.object(instance, "_rpc_check", return_value=False):
        assert instance.is_approved(REQUEST_ID, "skicka mejl till kund", risk, "run-001") is False


def test_approval_readback_rejects_invalid_scope_and_stale_request():
    instance = gate()
    risk = classify_risk("skicka mejl till kund", "unknown")
    with patch.object(instance, "_rpc_check") as checker:
        assert instance.is_approved("not-uuid", "skicka mejl till kund", risk, "run-001") is False
        assert instance.is_approved(REQUEST_ID, "skicka mejl till kund", risk, "") is False
        checker.assert_not_called()
    stage = (Path(__file__).resolve().parents[1] / "docs/security/sql/01_approval_backend_staging.sql").read_text()
    assert "FUNCTION public.jarvis_approval_check" in stage
    assert "REVOKE ALL ON FUNCTION public.jarvis_approval_check" in stage
    assert "r.response = 'approved'" in stage
    assert "d.draft_ref = ('sha256:' || p_action_sha256)" in stage
