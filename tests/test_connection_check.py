import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts import jarvis_connection_check as check

CHECK_ID = "cc62340c-98bc-409b-9a40-6523e1eade84"
ROOT = Path(__file__).resolve().parents[1]


def valid_event():
    return {
        "action": check.EXPECTED_EVENT,
        "repository": {"full_name": check.EXPECTED_REPOSITORY},
        "client_payload": {"check_id": CHECK_ID},
    }


class ConnectionCheckTests(unittest.TestCase):
    def test_valid_event_returns_only_correlation_id(self):
        self.assertEqual(check.validate_event(
            "repository_dispatch", check.EXPECTED_REPOSITORY, valid_event()
        ), CHECK_ID)

    def test_event_type_and_repository_are_exact(self):
        cases = [
            ("workflow_dispatch", check.EXPECTED_REPOSITORY, valid_event()),
            ("repository_dispatch", "other/repository", valid_event()),
            ("repository_dispatch", check.EXPECTED_REPOSITORY, {}),
            ("repository_dispatch", check.EXPECTED_REPOSITORY, []),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(check.InvalidCheck):
                check.validate_event(*args)

    def test_malformed_or_extra_payload_fields_are_rejected(self):
        for payload in ({}, None, [], {"check_id": ""}, {"check_id": None},
                        {"check_id": CHECK_ID + "\n"},
                        {"check_id": "$(synthetic-test)"},
                        {"check_id": CHECK_ID, "task": "must not run"},
                        {"check_id": CHECK_ID, "notion_page_id": "must not write"}):
            event = valid_event()
            event["client_payload"] = payload
            with self.subTest(payload=payload), self.assertRaises(check.InvalidCheck):
                check.validate_event("repository_dispatch", check.EXPECTED_REPOSITORY, event)

    def test_normal_jarvis_event_is_rejected(self):
        event = valid_event()
        event["action"] = "jarvis-run"
        with self.assertRaises(check.InvalidCheck):
            check.validate_event("repository_dispatch", check.EXPECTED_REPOSITORY, event)

    def test_repository_payload_must_match_workflow_context(self):
        for repository in (None, {}, {"full_name": "other/repository"}):
            event = valid_event()
            event["repository"] = repository
            with self.subTest(repository=repository), self.assertRaises(check.InvalidCheck):
                check.validate_event("repository_dispatch", check.EXPECTED_REPOSITORY, event)

    def test_valid_event_calls_only_read_only_preflight(self):
        output = io.StringIO()
        with patch.dict(os.environ, {
            "GITHUB_EVENT_NAME": "repository_dispatch",
            "GITHUB_REPOSITORY": check.EXPECTED_REPOSITORY,
        }), patch.object(check, "read_event", return_value=valid_event()), \
                patch.object(check.hf, "main", return_value=0) as preflight, \
                contextlib.redirect_stdout(output):
            self.assertEqual(check.main(), 0)
        preflight.assert_called_once_with()
        self.assertEqual(json.loads(output.getvalue()), {
            "event": check.EXPECTED_EVENT,
            "check_id": CHECK_ID,
            "normal_jarvis_run": False,
            "inference_requested": False,
        })

    def test_upstream_failure_is_not_reported_as_success(self):
        with patch.dict(os.environ, {
            "GITHUB_EVENT_NAME": "repository_dispatch",
            "GITHUB_REPOSITORY": check.EXPECTED_REPOSITORY,
        }), patch.object(check, "read_event", return_value=valid_event()), \
                patch.object(check.hf, "main", return_value=1), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(), 1)

    def test_invalid_event_never_calls_hugging_face(self):
        with patch.object(check, "read_event", return_value={}), \
                patch.object(check.hf, "main") as preflight, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(), 1)
        preflight.assert_not_called()

    def test_error_and_cancelled_reports_do_not_leak(self):
        sensitive = "synthetic-secret-and-task-marker"
        for error, code in [(ValueError(sensitive), 1), (OSError(sensitive), 1),
                            (KeyboardInterrupt(), 130)]:
            output = io.StringIO()
            with patch.object(check, "read_event", side_effect=error), \
                    patch.object(check.hf, "main") as preflight, \
                    contextlib.redirect_stdout(output):
                self.assertEqual(check.main(), code)
            preflight.assert_not_called()
            self.assertNotIn(sensitive, output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["completion_requests"], 0)

    def test_event_read_rejects_oversize_and_invalid_json(self):
        for raw in (b"not-json", b"x" * (check.MAX_EVENT_BYTES + 1)):
            with patch.object(Path, "open") as opened:
                opened.return_value.__enter__.return_value.read.return_value = raw
                with self.assertRaises((ValueError, check.InvalidCheck)):
                    check.read_event()

    def test_workflow_is_isolated_and_has_no_untrusted_shell_interpolation(self):
        path = ROOT / ".github/workflows/jarvis-connection-check.yml"
        workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(workflow["on"], {
            "repository_dispatch": {"types": ["jarvis-connection-check"]}
        })
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["jobs"]), {"verify_connection"})
        steps = workflow["jobs"]["verify_connection"]["steps"]
        self.assertEqual(steps[0]["with"]["persist-credentials"], "false")
        run_steps = [step for step in steps if "run" in step]
        self.assertEqual(len(run_steps), 1)
        self.assertEqual(run_steps[0]["run"], "python -m scripts.jarvis_connection_check")
        self.assertEqual(run_steps[0]["env"], {
            "HF_TOKEN": "${{ secrets.HF_TOKEN }}",
            "HF_EXPECTED_USERNAME": "rickyraippalinna",
        })
        serialized = json.dumps(workflow)
        for forbidden in ("jarvis_cloud.py", "SUPABASE_SERVICE_ROLE_KEY",
                          "NOTION_TOKEN", "SLACK_WEBHOOK_URL", "COMET_API_KEY",
                          "schedule", "workflow_call"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
