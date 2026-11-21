"""Offline regression checks for the guarded Approval Center anon lockdown."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261117031000_approval_anon_lockdown.sql"


class ApprovalAnonLockdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    def test_owner_provisioning_preflight_precedes_any_revocation(self):
        guard = self.sql.index("from public.jarvis_approval_admin where enabled is true")
        revoke = self.sql.index("revoke all privileges on table public.approval_decision")
        self.assertLess(guard, revoke)
        self.assertIn("provision and verify at least one owner-authenticated", self.sql)

    def test_server_decision_rpc_and_service_role_are_required(self):
        self.assertIn("public.jarvis_approval_decide(uuid,uuid,text,text)", self.sql)
        self.assertIn("has_function_privilege", self.sql)
        self.assertIn("grant execute on function public.jarvis_approval_decide(uuid,uuid,text,text) to service_role", self.sql)

    def test_anon_and_authenticated_table_grants_are_revoked(self):
        for table in ("approval_decision", "approval_request", "approval_audit_log"):
            self.assertIn(
                f"revoke all privileges on table public.{table} from public, anon, authenticated",
                self.sql,
            )

    def test_only_known_client_policies_are_dropped(self):
        for policy in (
            "jarvis_anon_tenant_insert",
            "jarvis_anon_tenant_select",
            "jarvis_anon_tenant_update",
            "jarvis_backend_insert_pending",
            "jarvis_backend_insert_request",
        ):
            self.assertIn(f"drop policy if exists {policy}", self.sql)
        self.assertNotIn("drop policy if exists jarvis_service_all", self.sql)

    def test_no_admin_identity_is_created_or_enabled_by_migration(self):
        self.assertNotIn("insert into public.jarvis_approval_admin", self.sql)
        self.assertNotIn("update public.jarvis_approval_admin", self.sql)
        self.assertNotIn("auth.users", self.sql)


if __name__ == "__main__":
    unittest.main()
