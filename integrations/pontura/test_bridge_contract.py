"""Offline contract tests. Run: python -m unittest discover -s integrations/pontura -p 'test_*.py'"""
import unittest
from bridge_contract import IntegrationDenied, validate_draft

def draft():
    return {
        "contract_version": "pontura.jarvis.v1", "origin": "jarvis-omega-v2",
        "project": "pontura", "tenant_id": "pontura-demo-tenant",
        "request_id": "pontura-demo-00001", "action": "source_review",
        "source_ids": ["synthetic-ref-001"], "sensitivity": "internal",
        "estimated_cost_sek": 0.0, "status": "draft",
        "provenance": "github:rickyraippalinna/jarvis-omega-v2@" + "0"*40,
    }

class ContractTests(unittest.TestCase):
    def go(self, data=None, cap=0):
        return validate_draft(data if data is not None else draft(),
                              authorized_tenant="pontura-demo-tenant", max_cost_sek=cap)
    def test_valid_draft(self):
        self.assertEqual(self.go().action, "source_review")
    def test_deterministic_dedup(self):
        self.assertEqual(self.go().fingerprint, self.go().fingerprint)
    def test_wrong_tenant(self):
        d=draft(); d["tenant_id"]="different-tenant"
        with self.assertRaises(IntegrationDenied): self.go(d)
    def test_external_action(self):
        d=draft(); d["action"]="send_email"
        with self.assertRaises(IntegrationDenied): self.go(d)
    def test_approval_state(self):
        d=draft(); d["status"]="approved_internal"
        with self.assertRaises(IntegrationDenied): self.go(d)
    def test_sensitive(self):
        d=draft(); d["sensitivity"]="confidential"
        with self.assertRaises(IntegrationDenied): self.go(d)
    def test_secret_field(self):
        d=draft(); d["api_key"]="nothing-real"
        with self.assertRaises(IntegrationDenied): self.go(d)
    def test_cost_cap(self):
        d=draft(); d["estimated_cost_sek"]=0.01
        with self.assertRaises(IntegrationDenied): self.go(d)
        self.assertEqual(self.go(d,0.1).estimated_cost_sek,0.01)
    def test_unpinned_source(self):
        d=draft(); d["provenance"]="github:latest"
        with self.assertRaises(IntegrationDenied): self.go(d)
    def test_other_project(self):
        d=draft(); d["project"]="jarvis-core"
        with self.assertRaises(IntegrationDenied): self.go(d)
    def test_invalid_source_ids(self):
        d=draft(); d["source_ids"]=["synthetic-ref-001"]*2
        with self.assertRaises(IntegrationDenied): self.go(d)

if __name__ == "__main__":
    unittest.main()
