"""Security regressions for Pontura server-only ingress."""
import sqlite3
import unittest
from bridge_contract import IntegrationDenied
from secure_ingress import SecureIngress, signature

KEY = b"test-only-server-key-" + b"x" * 32
NOW = 1800000000
NONCE = "pontura_nonce_000001"

def draft(tenant="tenant-one", request="request-00001"):
    return dict(contract_version="pontura.jarvis.v1", origin="jarvis-omega-v2",
        project="pontura", tenant_id=tenant, request_id=request,
        action="source_review", source_ids=["source-00001"],
        sensitivity="internal", estimated_cost_sek=0, status="draft",
        provenance="github:rickyraippalinna/jarvis-omega-v2@"+"a"*40)

class SecureIngressTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.gate = SecureIngress(self.db)
    def send(self, payload=None, *, nonce=NONCE, key=KEY, timestamp=NOW,
             authenticated_tenant="tenant-one", signed_payload=None):
        payload = payload if payload is not None else draft()
        sig = signature(key, timestamp, nonce, signed_payload or payload)
        return self.gate.accept(payload, authenticated_tenant=authenticated_tenant,
            server_secret=key, timestamp=timestamp, nonce=nonce,
            supplied_signature=sig, now=NOW)
    def test_accept_valid_draft(self):
        self.assertEqual(self.send().status, "draft")
    def test_duplicate_request(self):
        self.send()
        with self.assertRaises(IntegrationDenied):
            self.send(nonce="different_nonce_00001")
    def test_replay_nonce(self):
        self.send()
        with self.assertRaises(IntegrationDenied):
            self.send(draft(request="request-00002"))
    def test_wrong_tenant(self):
        with self.assertRaises(IntegrationDenied):
            self.send(draft(tenant="tenant-two"))
    def test_tamper(self):
        p=draft()
        other=draft();other["action"]="maintenance_summary"
        with self.assertRaises(IntegrationDenied):
            self.send(p, signed_payload=other)
    def test_expired(self):
        with self.assertRaises(IntegrationDenied):
            self.send(timestamp=NOW-301)
    def test_future_clock(self):
        with self.assertRaises(IntegrationDenied):
            self.send(timestamp=NOW+301)
    def test_wrong_key(self):
        p=draft()
        sig=signature(b"y"*32,NOW,NONCE,p)
        with self.assertRaises(IntegrationDenied):
            self.gate.accept(p,authenticated_tenant="tenant-one",
                server_secret=KEY,timestamp=NOW,nonce=NONCE,
                supplied_signature=sig,now=NOW)
    def test_secret_field_rejected(self):
        p=draft();p["api_key"]="fake"
        with self.assertRaises(IntegrationDenied):self.send(p)
    def test_billable_rejected(self):
        p=draft();p["estimated_cost_sek"]=0.01
        with self.assertRaises(IntegrationDenied):self.send(p)
    def test_no_receipt_on_rejection(self):
        with self.assertRaises(IntegrationDenied):self.send(draft(tenant="other"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM pontura_handoff_receipt").fetchone()[0],0)
    def test_invalid_nonce(self):
        with self.assertRaises(IntegrationDenied):
            self.send(nonce="short")
    def test_same_request_other_tenant_isolated(self):
        self.send()
        p=draft(tenant="tenant-two")
        self.send(p,nonce="another_nonce_000001",authenticated_tenant="tenant-two")
        self.assertEqual(self.db.execute("SELECT count(*) FROM pontura_handoff_receipt").fetchone()[0],2)

if __name__ == "__main__":
    unittest.main()
