"""Offline security regression checks for the JARVIS Brain endpoint."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = ROOT / "supabase" / "functions" / "jarvis-brain" / "index.ts"


class JarvisBrainSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = FUNCTION.read_text(encoding="utf-8")

    def test_query_string_is_rejected_before_auth_or_database_access(self):
        query_guard = self.source.index('if (url.search !== "")')
        header_auth = self.source.index('req.headers.get("x-jarvis-key")')
        first_private_read = self.source.index('rest("event?select=event_id')
        self.assertLess(query_guard, header_auth)
        self.assertLess(query_guard, first_private_read)
        self.assertNotIn('searchParams.get("k")', self.source)

    def test_header_is_the_only_private_key_transport(self):
        self.assertIn('req.headers.get("x-jarvis-key")', self.source)
        self.assertNotIn('url.searchParams.get("k")', self.source)

    def test_public_mode_returns_before_any_database_query(self):
        public_return = self.source.index('if (!full)')
        first_private_read = self.source.index('rest("event?select=event_id')
        self.assertLess(public_return, first_private_read)
        self.assertIn('status: "endpoint_only"', self.source)
        self.assertNotIn('out.events_by_type_14d =', self.source[:first_private_read])
        self.assertNotIn('out.memory_by_source =', self.source[:first_private_read])

    def test_invalid_header_fails_closed(self):
        self.assertIn('if (providedKey && !full) return json({ error: "Unauthorized" }, 401)', self.source)

    def test_cors_preflight_is_present_and_no_store_is_set(self):
        self.assertIn('"Access-Control-Allow-Methods": "GET, POST, OPTIONS"', self.source)
        self.assertIn('"Access-Control-Allow-Headers": "Content-Type, x-jarvis-key"', self.source)
        self.assertIn('"Cache-Control": "no-store"', self.source)

    def test_endpoint_is_read_only(self):
        self.assertNotIn('method: "POST"', self.source)
        self.assertNotIn('.insert(', self.source)
        self.assertNotIn('.update(', self.source)
        self.assertNotIn('.delete(', self.source)


if __name__ == "__main__":
    unittest.main()
