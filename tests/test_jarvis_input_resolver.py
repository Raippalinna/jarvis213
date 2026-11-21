"""Offline tests: no provider calls, GitHub secrets or cloud writes."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from resolve_jarvis_inputs import resolve, write_outputs  # noqa: E402


class WorkflowInputs(unittest.TestCase):
    def test_repository_dispatch_preserves_untrusted_shell_text_without_executing(self):
        task = "Research $(touch /tmp/NEVER_CREATE_THIS)\nnext step: `whoami`"
        value = resolve({
            "JARVIS_EVENT_NAME": "repository_dispatch", "JARVIS_PAYLOAD_TASK": task,
            "JARVIS_PAYLOAD_TIER": "MED", "JARVIS_PAYLOAD_ORIGIN": "chatgpt",
        })
        self.assertEqual(value["task"], task)
        self.assertEqual(value["origin_claim"], "chatgpt")
        self.assertEqual(value["tier"], "MED")
        self.assertEqual(len(value["request_id"]), 36)

    def test_newlines_are_delimiter_escaped_without_truncation(self):
        value = resolve({"JARVIS_EVENT_NAME": "workflow_dispatch", "JARVIS_DISPATCH_TASK": "A\nB\nx<<EOF\nC"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "output"
            write_outputs(path, value)
            result = path.read_text(encoding="utf-8")
            self.assertIn("A\nB\nx<<EOF\nC", result)
            self.assertIn("origin_claim<<JARVIS_", result)
            self.assertNotIn("task<<EOF", result)

    def test_workflow_call_overrides_dispatch_input(self):
        v = resolve({"JARVIS_EVENT_NAME": "schedule", "JARVIS_CALL_TASK": "Veckobrief", "JARVIS_CALL_TIER": "FREE", "JARVIS_DISPATCH_TASK": "wrong"})
        self.assertEqual((v["task"], v["tier"], v["origin_claim"]), ("Veckobrief", "FREE", "workflow_call"))

    def test_empty_task_rejected(self):
        with self.assertRaisesRegex(ValueError, "task is required"):
            resolve({"JARVIS_EVENT_NAME": "repository_dispatch"})

    def test_invalid_tier_and_forged_ids_rejected(self):
        base = {"JARVIS_EVENT_NAME": "repository_dispatch", "JARVIS_PAYLOAD_TASK": "Brief"}
        for field, value in [("JARVIS_PAYLOAD_TIER", "GODMODE"), ("JARVIS_PAYLOAD_CHAT_ID", "not-a-uuid"), ("JARVIS_PAYLOAD_REQUEST_ID", "bad")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                resolve({**base, field: value})

    def test_origin_is_not_used_as_verified_identity(self):
        v = resolve({"JARVIS_EVENT_NAME": "repository_dispatch", "JARVIS_PAYLOAD_TASK": "Brief", "JARVIS_PAYLOAD_ORIGIN": "administrator"})
        self.assertEqual(v["origin_claim"], "external_unverified")

    def test_reject_control_chars_and_oversized_task(self):
        base = {"JARVIS_EVENT_NAME": "repository_dispatch"}
        for task in ["x\rInjected", "x\x00y", "a" * 8001]:
            with self.subTest(task=task[:10]), self.assertRaises(ValueError):
                resolve({**base, "JARVIS_PAYLOAD_TASK": task})

    def test_dispatch_default_tier(self):
        v = resolve({"JARVIS_EVENT_NAME": "workflow_dispatch", "JARVIS_DISPATCH_TASK": "Brief"})
        self.assertEqual(v["tier"], "LOW")
        self.assertEqual(v["origin_claim"], "workflow_dispatch")


if __name__ == "__main__":
    unittest.main()
