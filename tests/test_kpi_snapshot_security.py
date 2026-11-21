"""Offline regression checks for the private JARVIS KPI snapshot cutover."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261117030000_secure_kpi_snapshot.sql"
FUNCTION = ROOT / "supabase" / "functions" / "jarvis-kpi-snapshot" / "index.ts"
CONFIG = ROOT / "supabase" / "config.toml"


class KpiSnapshotSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())
        cls.edge = FUNCTION.read_text(encoding="utf-8")
        cls.config = CONFIG.read_text(encoding="utf-8").lower()

    def test_database_function_is_security_definer_with_fixed_search_path(self):
        self.assertIn("security definer", self.sql)
        self.assertIn("set search_path = pg_catalog, pg_temp", self.sql)
        self.assertIn("alter function public.jarvis_kpi_snapshot() owner to postgres", self.sql)

    def test_execute_privilege_is_limited_to_postgres(self):
        self.assertIn(
            "revoke all on function public.jarvis_kpi_snapshot() from public, anon, authenticated, service_role",
            self.sql,
        )
        self.assertIn(
            "grant execute on function public.jarvis_kpi_snapshot() to postgres",
            self.sql,
        )

    def test_cron_no_longer_calls_public_http_endpoint(self):
        self.assertIn("select public.jarvis_kpi_snapshot();", self.sql)
        self.assertIn("cron.schedule(", self.sql)
        self.assertNotIn("net.http_post", self.sql)
        self.assertNotIn("functions/v1/jarvis-kpi-snapshot", self.sql)
        self.assertIn("username = 'postgres'", self.sql)

    def test_snapshot_is_idempotent_and_concurrency_safe(self):
        self.assertIn("pg_advisory_xact_lock", self.sql)
        self.assertIn("on conflict (idempotency_key) do nothing", self.sql)
        self.assertIn("source_systems @> array['jarvis-kpi-snapshot']::text[]", self.sql)
        self.assertIn("kpi:", self.sql)
        self.assertIn("v_pending_dead_letters bigint := null", self.sql)
        self.assertIn("v_dead_letters_scope text := 'not_tenant_scoped'", self.sql)
        self.assertIn("attname = 'tenant_id'", self.sql)
        self.assertIn("execute 'select count(*) from public.dead_letter where tenant_id = $1'", self.sql)
        self.assertIn("v_dead_letters_scope := 'tenant_scoped'", self.sql)
        self.assertIn("v_dead_letters_scope := 'not_tenant_scoped'", self.sql)
        self.assertIn("'dead_letters_scope', v_dead_letters_scope", self.sql)

    def test_dead_letter_metric_never_crosses_tenant_boundary(self):
        self.assertIn("pg_catalog.pg_attribute", self.sql)
        self.assertIn("attname = 'tenant_id'", self.sql)
        self.assertIn("v_pending_dead_letters := null", self.sql)
        self.assertIn("dead letters: not tenant-scoped", self.sql)
        self.assertNotIn("from public.dead_letter where tenant_id = v_tenant", self.sql)


    def test_old_edge_endpoint_is_a_non_writing_tombstone(self):
        self.assertIn("status: 410", self.edge)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", self.edge)
        self.assertNotIn("createClient", self.edge)
        self.assertNotIn("fetch(", self.edge)

    def test_edge_gateway_verifies_jwt(self):
        self.assertIn("[functions.jarvis-kpi-snapshot]", self.config)
        self.assertIn("verify_jwt = true", self.config)


if __name__ == "__main__":
    unittest.main()
