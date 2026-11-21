"""Nyckelfria regressionstester för runnerns chattåterkoppling."""
import ast
import io
import json
import os
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.supabase_auth import SupabaseAuthError, backend_headers, ensure_expected_project_url, resolve_backend_key


def load_writeback():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "jarvis_cloud.py").read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_patch_chat_row")
    namespace = {
        "os": os,
        "json": json,
        "SupabaseAuthError": SupabaseAuthError,
        "backend_headers": backend_headers,
        "resolve_backend_key": resolve_backend_key,
        "ensure_expected_project_url": ensure_expected_project_url,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), "writeback_under_test", "exec"), namespace)
    return namespace["_patch_chat_row"]


class ChatWritebackTests(unittest.TestCase):
    chat_id = "5552f254-c9ca-4053-be40-65c14dc8eae6"

    def setUp(self):
        self.function = load_writeback()
        self.secret_key = "sb_" + "secret_synthetic_test_only"
        self.env = patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://fzmnqvmfilqizzftphbt.supabase.co",
                "SUPABASE_SECRET_KEY": self.secret_key,
            },
            clear=True,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def response(self, body, status=200):
        response = MagicMock()
        response.status = status
        response.read.return_value = body
        response.__enter__.return_value = response
        return response

    def check_body(self, body, expected, status=200):
        response = self.response(json.dumps(body).encode(), status)
        with patch("urllib.request.urlopen", return_value=response) as network:
            self.assertEqual(self.function(self.chat_id, {"status": "answered"}), expected)
            request = network.call_args.args[0]
            self.assertIn("select=id,status", request.full_url)
            self.assertEqual(request.get_header("Prefer"), "return=representation")
            self.assertEqual(request.get_header("Apikey"), self.secret_key)
            self.assertIsNone(request.get_header("Authorization"))

    def test_success(self):
        self.check_body([{"id": self.chat_id, "status": "answered"}], "chat: ok 200 verified")

    def test_zero_rows(self):
        self.check_body([], "chat: write_unverified")

    def test_wrong_row(self):
        self.check_body([{"id": "other", "status": "answered"}], "chat: write_unverified")

    def test_wrong_status(self):
        self.check_body([{"id": self.chat_id, "status": "queued"}], "chat: write_unverified")

    def test_multiple_rows(self):
        self.check_body([{"id": self.chat_id}, {"id": self.chat_id}], "chat: write_unverified")

    def test_unexpected_shape(self):
        self.check_body({"id": self.chat_id}, "chat: write_unverified")

    def test_empty_204(self):
        self.check_body(None, "chat: unexpected_status 204", 204)

    def test_missing_credentials(self):
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen") as network:
            self.assertEqual(self.function(self.chat_id, {}), "chat: skipped")
            network.assert_not_called()

    def test_wrong_project_rejected_without_network(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "https://example.invalid"}), patch("urllib.request.urlopen") as network:
            self.assertEqual(
                self.function(self.chat_id, {"status": "answered"}),
                "chat: configuration_error unexpected_project_url",
            )
            network.assert_not_called()

    def test_invalid_id(self):
        with patch("urllib.request.urlopen") as network:
            self.assertEqual(self.function("bad&select=*", {}), "chat: invalid_id")
            network.assert_not_called()

    def test_http_error_redacted(self):
        error = urllib.error.HTTPError("https://example.invalid", 403, "synthetic-test-secret", {}, io.BytesIO(b"sensitive payload"))
        with patch("urllib.request.urlopen", side_effect=error):
            self.assertEqual(self.function(self.chat_id, {}), "chat: http_error 403")

    def test_timeout_redacted(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("sensitive payload")):
            self.assertEqual(self.function(self.chat_id, {}), "chat: err TimeoutError")

    def test_invalid_json(self):
        with patch("urllib.request.urlopen", return_value=self.response(b"not-json")):
            self.assertEqual(self.function(self.chat_id, {}), "chat: err JSONDecodeError")

    def test_cancelled(self):
        with patch("urllib.request.urlopen", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.function(self.chat_id, {})
