import contextlib
import io
import json
import os
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from scripts import huggingface_preflight as hf


class HuggingFacePreflightTests(unittest.TestCase):
    def checks(self, identity=None, catalog=None):
        return patch.object(hf, "request_json", side_effect=[
            {"name": "rickyraippalinna"} if identity is None else identity,
            {"data": [{"id": "fixture/model"}]} if catalog is None else catalog,
        ])

    def test_identity_and_catalog_are_separate_read_only_checks(self):
        with self.checks() as get:
            result = hf.verify_connection("unit-test-placeholder", "rickyraippalinna")
        self.assertEqual(result["account"], "rickyraippalinna")
        self.assertEqual(result["model_count"], 1)
        self.assertEqual(result["completion_requests"], 0)
        self.assertFalse(result["inference_tested"])
        self.assertTrue(result["catalog_is_public"])
        self.assertEqual(get.call_args_list[0].args,
                         (hf.IDENTITY_URL, "unit-test-placeholder"))
        self.assertEqual(get.call_args_list[1].args, (hf.CATALOG_URL,))

    def test_missing_token_stops_before_network(self):
        with patch.object(hf, "request_json") as get:
            with self.assertRaises(hf.PreflightFailure):
                hf.verify_connection("", "rickyraippalinna")
        get.assert_not_called()

    def test_header_injection_stops_before_network(self):
        with patch.object(hf, "request_json") as get:
            with self.assertRaises(hf.PreflightFailure):
                hf.verify_connection("placeholder\ninjected", "rickyraippalinna")
        get.assert_not_called()

    def test_expected_account_is_required(self):
        with patch.object(hf, "request_json") as get:
            with self.assertRaises(hf.PreflightFailure):
                hf.verify_connection("unit-test-placeholder", "")
        get.assert_not_called()

    def test_wrong_account_does_not_continue(self):
        with self.checks(identity={"name": "different-account"}) as get:
            with self.assertRaises(hf.PreflightFailure):
                hf.verify_connection("unit-test-placeholder", "rickyraippalinna")
        self.assertEqual(get.call_count, 1)

    def test_invalid_or_empty_catalogs_fail_closed(self):
        for catalog in ([], {}, {"data": []}, {"data": ["bad"]},
                        {"data": [{"id": ""}]},
                        {"data": [{"id": "same"}, {"id": "same"}]}):
            with self.subTest(catalog=catalog), self.checks(catalog=catalog):
                with self.assertRaises(hf.PreflightFailure):
                    hf.verify_connection("unit-test-placeholder", "rickyraippalinna")

    def test_request_uses_get_and_credential_only_at_identity_host(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"name":"fixture"}'
        with patch.object(hf.urllib.request, "build_opener") as build:
            build.return_value.open.return_value = response
            hf.request_json(hf.IDENTITY_URL, "unit-test-placeholder")
        request = build.return_value.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, hf.IDENTITY_URL)
        self.assertEqual(request.get_header("Authorization"),
                         "Bearer unit-test-placeholder")
        self.assertEqual(build.return_value.open.call_args.kwargs["timeout"], 20)
        self.assertIsNone(hf.NoRedirect().redirect_request(
            request, None, 302, "", {}, "https://not-authorized.example"))

    def test_credentials_never_go_to_catalog_or_arbitrary_host(self):
        for url in (hf.CATALOG_URL, "https://not-authorized.example"):
            with self.subTest(url=url), patch.object(
                    hf.urllib.request, "build_opener") as build:
                with self.assertRaises(hf.PreflightFailure):
                    hf.request_json(url, "unit-test-placeholder")
                build.assert_not_called()

    def test_invalid_json_and_oversized_responses_are_rejected(self):
        for raw in (b"not json", b"x" * (hf.MAX_RESPONSE_BYTES + 1)):
            response = MagicMock()
            response.__enter__.return_value.read.return_value = raw
            with patch.object(hf.urllib.request, "build_opener") as build:
                build.return_value.open.return_value = response
                with self.assertRaises(hf.PreflightFailure):
                    hf.request_json(hf.CATALOG_URL)

    def test_errors_do_not_print_secret_or_remote_error_body(self):
        marker = "sensitive-test-marker"
        errors = [
            urllib.error.HTTPError(hf.IDENTITY_URL, 401, marker, {},
                                   io.BytesIO(marker.encode())),
            urllib.error.URLError(marker),
            TimeoutError(marker),
            RuntimeError(marker),
            KeyboardInterrupt(),
        ]
        for error in errors:
            output = io.StringIO()
            with self.subTest(error=type(error).__name__), patch.dict(
                    os.environ, {"HF_TOKEN": marker,
                                 "HF_EXPECTED_USERNAME": "rickyraippalinna"}):
                with patch.object(hf, "request_json", side_effect=error):
                    with contextlib.redirect_stdout(output):
                        code = hf.main()
            self.assertNotEqual(code, 0)
            self.assertNotIn(marker, output.getvalue())
            self.assertNotIn("Authorization", output.getvalue())
            self.assertIsInstance(json.loads(output.getvalue()), dict)

    def test_workflow_runs_preflight_separately_from_normal_runner(self):
        root = Path(__file__).resolve().parents[1] / ".github/workflows"
        workflow = yaml.load((root / "jarvis-connection-check.yml").read_text(),
                             Loader=yaml.BaseLoader)
        normal = yaml.load((root / "jarvis-cloud.yml").read_text(),
                           Loader=yaml.BaseLoader)
        self.assertEqual(workflow["on"]["repository_dispatch"]["types"],
                         ["jarvis-connection-check"])
        self.assertEqual(normal["on"]["repository_dispatch"]["types"], ["jarvis-run"])
        job = workflow["jobs"]["verify_connection"]
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        serialized = json.dumps(job)
        for forbidden in ("jarvis_cloud.py", "SUPABASE_SERVICE_ROLE_KEY",
                          "NOTION_TOKEN", "SLACK_WEBHOOK_URL", "COMET_API_KEY"):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("python -m scripts.jarvis_connection_check", serialized)


if __name__ == "__main__":
    unittest.main()
