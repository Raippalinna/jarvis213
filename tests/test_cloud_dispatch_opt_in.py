"""Offline regression for the JARVIS Cloud machine-dispatch release gate.

The test deliberately reads workflow source only; it never invokes GitHub APIs,
agent providers, Supabase, or a repository_dispatch event.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "jarvis-cloud.yml"

# Explicit opt-in for machine events; manual and workflow_call remain independently reviewed.
EXPECTED = (
    "if: ${{ github.event_name != 'repository_dispatch' || "
    "vars.JARVIS_REPOSITORY_DISPATCH_ENABLED == 'true' }}"
)


class CloudDispatchOptInTests(unittest.TestCase):
    def test_machine_dispatch_requires_exact_opt_in(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("repository_dispatch:", content)
        self.assertIn("types: [jarvis-run]", content)
        self.assertIn(EXPECTED, content)

    def test_guard_is_at_execute_job_level_before_runner(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(
            content,
            r"(?m)^jobs:\s*\n  execute:\s*\n"
            r"(?:    #[^\n]*\n)*"
            r"    if: \$\{\{ github\.event_name != 'repository_dispatch'"
            r" \|\| vars\.JARVIS_REPOSITORY_DISPATCH_ENABLED == 'true' \}\}\s*\n"
            r"    runs-on:",
        )

    def test_no_inline_enabling_or_secret_in_guard(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        guard_lines = [line for line in content.splitlines() if "JARVIS_REPOSITORY_DISPATCH_ENABLED" in line]
        self.assertEqual(len(guard_lines), 1)
        guard = guard_lines[0]
        self.assertNotIn("secrets.", guard)
        self.assertNotIn("env.", guard)
        self.assertEqual(guard.strip(), EXPECTED)


if __name__ == "__main__":
    unittest.main()
