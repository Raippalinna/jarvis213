"""Offline schema/contract tests for the Copilot Studio GitHub dispatch integration.

No credentials, APIs, workflows or paid providers are called. Use:
    python -m unittest discover -s tests -p 'test_copilot_openapi_contract.py'
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "integrations"
ROUTE = "/repos/rickyraippalinna/jarvis-omega-v2/dispatches"
TIERS = ["FREE", "LOW", "MED", "HIGH"]


class CopilotDispatchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v3 = json.loads((DOCS / "copilot-studio-jarvis.openapi.json").read_text(encoding="utf-8"))
        cls.v2 = json.loads((DOCS / "copilot-studio-jarvis.swagger2.json").read_text(encoding="utf-8"))

    def test_formats_and_exact_endpoint(self) -> None:
        self.assertEqual(self.v3["openapi"], "3.0.3")
        self.assertEqual(self.v2["swagger"], "2.0")
        self.assertEqual(self.v3["servers"], [{"url": "https://api.github.com"}])
        self.assertEqual(self.v2["host"], "api.github.com")
        self.assertEqual(self.v2["schemes"], ["https"])
        for doc in (self.v2, self.v3):
            self.assertEqual(list(doc["paths"]), [ROUTE])
            self.assertEqual(list(doc["paths"][ROUTE]), ["post"])
            self.assertEqual(doc["paths"][ROUTE]["post"]["operationId"], "dispatchJarvisTask")

    def test_payloads_match_existing_resolver(self) -> None:
        op3 = self.v3["paths"][ROUTE]["post"]
        body3 = op3["requestBody"]["content"]["application/json"]["schema"]
        task3 = body3["properties"]["client_payload"]["properties"]
        req2 = self.v2["definitions"]["DispatchRequest"]
        payload2 = self.v2["definitions"]["DispatchPayload"]
        self.assertEqual(body3["properties"]["event_type"]["enum"], ["jarvis-run"])
        self.assertEqual(req2["properties"]["event_type"]["enum"], ["jarvis-run"])
        self.assertEqual(task3["tier"]["enum"], TIERS)
        self.assertEqual(payload2["properties"]["tier"]["enum"], TIERS)
        self.assertEqual(task3["task"]["maxLength"], 8000)
        self.assertEqual(payload2["properties"]["task"]["maxLength"], 8000)
        self.assertEqual(body3["required"], ["event_type", "client_payload"])
        self.assertEqual(req2["required"], ["event_type", "client_payload"])
        self.assertFalse(body3["additionalProperties"])
        self.assertFalse(req2["additionalProperties"])
        self.assertFalse(payload2["additionalProperties"])
        self.assertEqual(task3["request_id"]["format"], "uuid")
        self.assertEqual(payload2["properties"]["request_id"]["format"], "uuid")

    def test_auth_is_required_never_embedded(self) -> None:
        op3 = self.v3["paths"][ROUTE]["post"]
        op2 = self.v2["paths"][ROUTE]["post"]
        self.assertEqual(op3["security"], [{"GitHubBearer": []}])
        self.assertEqual(op2["security"], [{"GitHubAuthorization": []}])
        self.assertEqual(self.v3["components"]["securitySchemes"]["GitHubBearer"]["scheme"], "bearer")
        auth = self.v2["securityDefinitions"]["GitHubAuthorization"]
        self.assertEqual((auth["type"], auth["in"], auth["name"]), ("apiKey", "header", "Authorization"))
        for doc in (self.v2, self.v3):
            raw = json.dumps(doc)
            self.assertIsNone(re.search(r"(?i)(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", raw))

    def test_copilot_approval_settings_are_explicit_and_not_the_only_gate(self) -> None:
        guidance = (DOCS / "copilot-studio-codex-lovable.md").read_text(encoding="utf-8")
        self.assertIn("Ask the end user before running = Yes", guidance)
        self.assertIn("Allow agent to decide dynamically when to use the tool = No", guidance)
        self.assertIn("teknisk säkerhetsgrind", guidance)
        self.assertIn("backend-/Power Automate-grind", guidance)

    def test_no_workflow_or_gate_changes(self) -> None:
        flow = (ROOT / ".github" / "workflows" / "jarvis-cloud.yml").read_text(encoding="utf-8")
        resolver = (ROOT / "scripts" / "resolve_jarvis_inputs.py").read_text(encoding="utf-8")
        self.assertIn("types: [jarvis-run]", flow)
        self.assertIn("JARVIS_REPOSITORY_DISPATCH_ENABLED == 'true'", flow)
        self.assertIn("MAX_TASK_LENGTH = 8000", resolver)
        for tier in TIERS:
            self.assertIn(f'"{tier}"', resolver)


if __name__ == "__main__":
    unittest.main()
