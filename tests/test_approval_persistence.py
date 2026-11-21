"""Offline approval receipt tests. No network or production fixtures."""
import asyncio
import contextlib
import io
import json
import os
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

from langchain_core.messages import HumanMessage
from jarvis.approval.gate import ApprovalGate, RiskDecision
from jarvis.safety import guard
import jarvis.core.supervisor as supervisor
import jarvis_cloud as cloud


DECISION = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REQUEST = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
AUDIT = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
RISK = RiskDecision("R3", True, "offline test")


class ApprovalPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.gate = ApprovalGate("https://unit.invalid", "offline-placeholder")

    def receipt(self, **overrides):
        return {
            "decision_id": DECISION, "request_id": REQUEST, "audit_id": AUDIT,
            "state": "pending_approval", "scope": "review_only",
            "execution_authorized": False,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            **overrides,
        }

    def test_single_rpc_returns_review_receipt_without_insert_fallback(self):
        with patch.object(guard, "require_autonomy") as switch, \
             patch("urllib.request.urlopen") as net, patch.object(self.gate, "_insert") as insert:
            net.return_value.__enter__.return_value.read.return_value = json.dumps(self.receipt()).encode()
            self.assertEqual(self.gate.open_gate("TEST: granskning", RISK, "offline"), REQUEST)
            net.assert_called_once()
            insert.assert_not_called()
            switch.assert_called_once()
        request = net.call_args.args[0]
        self.assertEqual(request.full_url, "https://unit.invalid/rest/v1/rpc/jarvis_open_review_v1")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {
            "p_tenant": self.gate.tenant_id, "p_actor": self.gate.principal_id,
            "p_session": "offline", "p_task": "TEST: granskning",
            "p_risk": "R3", "p_reason": "offline test",
        })

    def test_retry_sends_identical_input(self):
        with patch.object(guard, "require_autonomy"), patch("urllib.request.urlopen") as net:
            net.return_value.__enter__.return_value.read.return_value = json.dumps(self.receipt()).encode()
            for _ in range(2):
                self.assertEqual(self.gate.open_gate("TEST", RISK, "stable-session"), REQUEST)
        self.assertEqual(net.call_args_list[0].args[0].data, net.call_args_list[1].args[0].data)

    def test_rpc_invalid_or_expired_receipts_never_claim_saved_review(self):
        payloads = [None, [], {}, self.receipt(state="approved"),
                    self.receipt(scope="execute"), self.receipt(execution_authorized=True),
                    self.receipt(execution_authorized=0), self.receipt(audit_id="bad"),
                    self.receipt(decision_id=None), self.receipt(request_id=""),
                    self.receipt(expires_at="2000-01-01T00:00:00+00:00"),
                    self.receipt(expires_at="2999-01-01T00:00:00"),
                    self.receipt(expires_at=None)]
        for payload in payloads:
            with self.subTest(payload=payload), patch.object(guard, "require_autonomy"), \
                 patch("urllib.request.urlopen") as net, patch.object(self.gate, "_insert") as insert:
                net.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
                self.assertIsNone(self.gate.open_gate("TEST", RISK, "offline"))
                insert.assert_not_called()

    def test_network_failure_never_falls_back_or_leaks_error_details(self):
        errors = [TimeoutError("PRIVATE_BODY"),
                  urllib.error.HTTPError("https://unit.invalid", 404, "PRIVATE_BODY", {},
                                         io.BytesIO(b"PRIVATE_BODY"))]
        for error in errors:
            output = io.StringIO()
            with patch.object(guard, "require_autonomy"), \
                 patch("urllib.request.urlopen", side_effect=error) as net, \
                 patch.object(self.gate, "_insert") as insert, contextlib.redirect_stdout(output):
                self.assertIsNone(self.gate.open_gate("TEST", RISK, "offline"))
                net.assert_called_once()
                insert.assert_not_called()
            self.assertNotIn("PRIVATE_BODY", output.getvalue())

    def test_disabled_autonomy_prevents_network_request(self):
        with patch.object(guard, "require_autonomy", side_effect=RuntimeError("blocked")), \
             patch("urllib.request.urlopen") as net:
            self.assertIsNone(self.gate.open_gate("TEST", RISK, "offline"))
            net.assert_not_called()

    def test_sensitive_task_and_reason_are_redacted(self):
        secret = "sk-" + "x" * 40
        with patch.object(guard, "require_autonomy"), patch("urllib.request.urlopen") as net:
            net.return_value.__enter__.return_value.read.return_value = json.dumps(self.receipt()).encode()
            self.gate.open_gate("TEST " + secret, RiskDecision("R3", True, secret), "offline")
        self.assertNotIn(secret, net.call_args.args[0].data.decode())

    def test_input_validation_has_no_writes(self):
        for text, risk, session in [
            ("", RISK, "offline"), ("test", RISK, ""),
            ("test", RiskDecision("R0", False, "read"), "offline"),
            ("test", RiskDecision("R9", True, "invalid"), "offline"),
            ("x" * 2001, RISK, "offline"), ("TEST", RISK, "x" * 129),
            ("TEST", RiskDecision("R3", True, ""), "offline"),
            ("TEST", RiskDecision("R3", True, "x" * 301), "offline"),
        ]:
            with patch("urllib.request.urlopen") as write:
                self.assertIsNone(self.gate.open_gate(text, risk, session))
                write.assert_not_called()

    def test_http_not_allowed(self):
        self.assertFalse(ApprovalGate("http://unit.invalid", "fake").enabled)

    def test_auto_log_does_not_claim_execution(self):
        with patch.object(self.gate, "_insert") as write:
            self.gate.log_auto("test", RiskDecision("R0", False, "read"), "offline")
        row = write.call_args.args[1]
        self.assertEqual(row["actor_type"], "agent")
        self.assertEqual(row["event_type"], "auto_classified")
        self.assertNotIn("task_preview", row["metadata"])

    def test_invalid_receipts_are_rejected(self):
        for payload in ([], {}, [None], [{}], [{"id": "invalid"}],
                        [{"id": DECISION}, {"id": REQUEST}]):
            with self.subTest(payload=payload), patch.object(guard, "require_autonomy"), \
                 patch("urllib.request.urlopen") as net:
                net.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
                self.assertIsNone(self.gate._insert("approval_decision", {}))

    def test_valid_receipt(self):
        with patch.object(guard, "require_autonomy"), patch("urllib.request.urlopen") as net:
            net.return_value.__enter__.return_value.read.return_value = json.dumps([{"id": AUDIT}]).encode()
            self.assertEqual(self.gate._insert("approval_audit_log", {}), {"id": AUDIT})

    def test_error_body_never_logged(self):
        error = urllib.error.HTTPError(
            "https://unit.invalid", 401, "unauthorized", {}, io.BytesIO(b"PRIVATE_BODY")
        )
        output = io.StringIO()
        with patch.object(guard, "require_autonomy"), \
             patch("urllib.request.urlopen", side_effect=error), contextlib.redirect_stdout(output):
            self.assertIsNone(self.gate._insert("approval_decision", {}))
        self.assertNotIn("PRIVATE_BODY", output.getvalue())

    def test_gate_still_halts_after_storage_failure(self):
        state = {"messages": [HumanMessage(content="TEST: betala ingen faktura")],
                 "session_id": "offline", "intent": None}
        with patch.object(supervisor._approval, "open_gate", return_value=None):
            result = asyncio.run(supervisor.approval_gate(state))
        self.assertEqual(supervisor._approval_route(result), "halt")
        self.assertFalse(result["approval"]["execution_authorized"])
        self.assertEqual(cloud._execution_status(result), "approval_persistence_failed")
        self.assertNotEqual(cloud._exit_code(cloud._execution_status(result), "not_requested"), 0)

    def test_hold_output_distinguishes_saved_and_failed(self):
        for receipt in (REQUEST, None):
            state = {"messages": [HumanMessage(content="TEST")], "approval": {
                "risk_class": "R3", "reason": "offline", "request_id": receipt}}
            with patch.dict(os.environ, {"JARVIS_NOTIFY": "0"}), \
                 patch.object(supervisor, "notify_all") as notify:
                result = asyncio.run(supervisor.await_approval(state))
            answer = result["messages"][-1].content
            self.assertIn("återupptagning är inte implementerad", answer)
            self.assertIsNone(result["quality_score"])
            self.assertEqual("LAGRINGSFEL" in answer, receipt is None)
            notify.assert_not_called()

    def test_full_graph_hold_skips_provider_memory_and_uses_session_id(self):
        for receipt in (REQUEST, None):
            with patch.dict(os.environ, {"JARVIS_NOTIFY": "0"}), \
                 patch.object(guard, "require_autonomy"), \
                 patch.object(supervisor._approval, "open_gate", return_value=receipt) as gate, \
                 patch.object(supervisor, "AsyncOpenAI") as provider, \
                 patch.object(supervisor, "build_context") as memory:
                result = asyncio.run(supervisor.Supervisor().chat(
                    [HumanMessage(content="TEST: betala ingen faktura")]))
            UUID(gate.call_args.args[2])
            provider.assert_not_called()
            memory.assert_not_called()
            self.assertEqual(cloud._execution_status(result),
                             "awaiting_approval" if receipt else "approval_persistence_failed")

    def test_cloud_reruns_keep_session_identity(self):
        state = {"messages": [], "approval": {
            "required": True, "request_id": REQUEST, "execution_authorized": False}}
        sessions = []
        for attempt in ("1", "2"):
            with patch.dict(os.environ, {
                "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": attempt,
                "JARVIS_SESSION_ID": "", "NOTION_PAGE_ID": "",
            }), patch.object(cloud.supervisor, "chat", new_callable=AsyncMock, return_value=state) as chat, \
                 patch.object(cloud.Path, "write_text"), contextlib.redirect_stdout(io.StringIO()):
                asyncio.run(cloud.main())
                sessions.append(chat.call_args.kwargs["session_id"])
        self.assertEqual(sessions, ["github:12345", "github:12345"])

    def test_explicit_cloud_session_takes_precedence(self):
        with patch.dict(os.environ, {
            "GITHUB_RUN_ID": "12345", "JARVIS_SESSION_ID": " explicit-review ",
            "NOTION_PAGE_ID": "",
        }), patch.object(cloud.supervisor, "chat", new_callable=AsyncMock,
                         return_value={"messages": []}) as chat, \
             patch.object(cloud.Path, "write_text"), contextlib.redirect_stdout(io.StringIO()):
            asyncio.run(cloud.main())
        self.assertEqual(chat.call_args.kwargs["session_id"], "explicit-review")


if __name__ == "__main__":
    unittest.main()
