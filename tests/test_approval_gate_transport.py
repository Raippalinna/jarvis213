"""Offline regression tests for ApprovalGate transport validation and redacted logs."""
import contextlib
import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.approval.gate import ApprovalGate, _RejectRedirect, _open_no_redirect


class ApprovalGateTransportTests(unittest.TestCase):
    def test_https_endpoint_with_key_is_enabled(self):
        self.assertTrue(ApprovalGate("https://fzmnqvmfilqizzftphbt.supabase.co", "synthetic-key").enabled)

    def test_insecure_or_embedded_credentials_are_disabled(self):
        for url in (
            "http://example.supabase.co",
            "https://user:password@example.supabase.co",
            "https://fzmnqvmfilqizzftphbt.supabase.co?secret=test",
            "https://fzmnqvmfilqizzftphbt.supabase.co/#token",
            "https://[invalid",
            "not-a-url",
            "https://example.supabase.co",
            "https://fzmnqvmfilqizzftphbt.supabase.co.evil.example",
            "https://fzmnqvmfilqizzftphbt.supabase.co:8443",
            "https://fzmnqvmfilqizzftphbt.supabase.co/other-project",
        ):
            with self.subTest(url=url):
                self.assertFalse(ApprovalGate(url, "synthetic-key").enabled)

    def test_missing_key_is_disabled(self):
        self.assertFalse(ApprovalGate("https://fzmnqvmfilqizzftphbt.supabase.co", "").enabled)

    def test_http_error_body_never_logged(self):
        gate = ApprovalGate("https://fzmnqvmfilqizzftphbt.supabase.co", "synthetic-key")
        error = urllib.error.HTTPError(
            "https://fzmnqvmfilqizzftphbt.supabase.co/rest/v1/approval_request",
            401, "unauthorized", {}, io.BytesIO(b"secret-body-token"),
        )
        log = io.StringIO()
        with patch("jarvis.approval.gate._open_no_redirect", side_effect=error), contextlib.redirect_stdout(log):
            self.assertIsNone(gate._insert("approval_request", {"test": "synthetic"}))
        self.assertIn("401", log.getvalue())
        self.assertNotIn("secret-body-token", log.getvalue())
        self.assertNotIn("synthetic-key", log.getvalue())

    def test_redirect_is_always_rejected(self):
        handler = _RejectRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 307, "redirect", {}, "https://elsewhere.invalid/"))

    def test_opener_uses_reject_redirect_handler(self):
        with patch("urllib.request.build_opener") as factory:
            _open_no_redirect(object(), timeout=15)
            self.assertIs(factory.call_args.args[0], _RejectRedirect)
            self.assertEqual(factory.return_value.open.call_args.kwargs["timeout"], 15)

    def test_provider_exception_detail_never_logged(self):
        gate = ApprovalGate("https://fzmnqvmfilqizzftphbt.supabase.co", "synthetic-key")
        log = io.StringIO()
        with patch("jarvis.approval.gate._open_no_redirect", side_effect=RuntimeError("secret-provider-message")), contextlib.redirect_stdout(log):
            self.assertIsNone(gate._insert("approval_request", {"test": "synthetic"}))
        self.assertIn("external_request_failed", log.getvalue())
        self.assertNotIn("secret-provider-message", log.getvalue())


if __name__ == "__main__":
    unittest.main()
