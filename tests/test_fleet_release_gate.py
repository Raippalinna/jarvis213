import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fleet_release_gate import REQUIRED, assess


class FleetReleaseGateTests(unittest.TestCase):
    def test_all_evidence_explicitly_true(self):
        result = assess({"agents": [{"id": "jarvis", "checks": {k: True for k in REQUIRED}}]})
        self.assertTrue(result["ready"])
        self.assertIn("not_live_verification", result["scope"])

    def test_missing_checks_fail_closed(self):
        result = assess({"agents": [{"id": "sentinel", "checks": {"tests": True}}]})
        self.assertFalse(result["ready"])
        self.assertIn("tenant_isolation", result["agents"][0]["missing"])

    def test_truthy_string_is_not_evidence(self):
        checks = {k: "true" for k in REQUIRED}
        self.assertFalse(assess({"agents": [{"id": "agent", "checks": checks}]})["ready"])

    def test_duplicate_id_rejected(self):
        with self.assertRaises(ValueError):
            assess({"agents": [{"id": "a"}, {"id": "a"}]})

    def test_empty_fleet_rejected(self):
        with self.assertRaises(ValueError):
            assess({"agents": []})

    def test_one_blocked_agent_blocks_fleet(self):
        result = assess({"agents": [{"id": "a", "checks": {k: True for k in REQUIRED}}, {"id": "b"}]})
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
