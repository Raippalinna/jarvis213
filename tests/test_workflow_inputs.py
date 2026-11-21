import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.resolve_inputs import main, resolve


class WorkflowInputTests(unittest.TestCase):
    def test_scheduled_workflow_call_keeps_task(self):
        self.assertEqual(resolve("schedule", {}, {"task": "Veckobrief"})["task"], "Veckobrief")

    def test_repository_dispatch_takes_precedence(self):
        self.assertEqual(resolve("repository_dispatch", {"client_payload": {"task": "Rätt"}},
                                 {"task": "Fel"})["task"], "Rätt")

    def test_legacy_manual_dispatch(self):
        self.assertEqual(resolve("workflow_dispatch", {"inputs": {"task": "Hej"}}, {})["tier"], "LOW")

    def test_invalid_tier_rejected(self):
        with self.assertRaises(ValueError):
            resolve("schedule", {}, {"task": "Hej", "tier": "UNLIMITED"})

    def test_empty_task_rejected(self):
        with self.assertRaises(ValueError):
            resolve("schedule", {}, {"task": " "})

    def test_shell_and_multiline_text_remain_data(self):
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory) / "event.json"
            output = Path(directory) / "outputs"
            sentinel = Path(directory) / "must-not-exist"
            task = f'$(touch "{sentinel}")\nSecond line\nEOF\n"quoted"'
            event.write_text(json.dumps({"client_payload": {"task": task}}))
            with patch.dict(os.environ, {
                "GITHUB_EVENT_NAME": "repository_dispatch",
                "GITHUB_EVENT_PATH": str(event), "GITHUB_OUTPUT": str(output),
                "CALL_INPUTS_JSON": "{}",
            }, clear=True):
                main()
            self.assertFalse(sentinel.exists())
            self.assertIn(task, output.read_text())


if __name__ == "__main__":
    unittest.main()
