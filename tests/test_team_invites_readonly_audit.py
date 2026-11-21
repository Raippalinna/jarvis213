"""Nyckelfria kontrakttester för team_invites-metadataaudit (issue #88).

Dessa tester läser en SQL-fil som text och kör inte SQL, nätverk eller databas.
De bevisar inte att live-RLS är säker; endast att inventeringsfilen är skrivskyddad.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "security" / "team_invites_acl_readonly.sql"


def sql_statements(source: str) -> list[str]:
    """Ta bort hela SQL-kommentarer; utvärdera endast faktiska statements."""
    uncommented = "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith("--")
    )
    return [part.strip() for part in uncommented.split(";") if part.strip()]


class TeamInvitesReadonlyAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = AUDIT.read_text(encoding="utf-8")
        cls.statements = sql_statements(cls.text)
        cls.sql = "\n".join(cls.statements).lower()

    def test_audit_contains_only_select_statements(self):
        self.assertGreaterEqual(len(self.statements), 5)
        for statement in self.statements:
            with self.subTest(statement=statement[:70]):
                self.assertRegex(statement, r"(?is)^select\s+")

    def test_no_data_modification_or_execution(self):
        forbidden = (
            r"\b(insert|update|delete|truncate|alter|drop|create|grant|revoke|"
            r"copy|call|execute|perform|vacuum|do)\b"
        )
        # Statement content includes quoted privilege names such as UPDATE.
        # Strip SQL single-quoted string values before checking executable verbs.
        executable = re.sub(r"'(?:''|[^'])*'", "''", self.sql)
        self.assertNotRegex(executable, forbidden)
        self.assertNotIn("pg_get_functiondef", executable)
        self.assertNotIn("pg_read_file", executable)
        self.assertNotIn("pg_ls_dir", executable)

    def test_metadata_only_not_invitation_rows(self):
        self.assertNotRegex(
            self.sql,
            r"(?is)\bfrom\s+(?:public\.)?team_invites\b",
        )
        self.assertNotRegex(self.sql, r"(?is)\bselect\s+\*\b")
        for catalog in (
            "pg_class", "pg_namespace", "pg_policies", "pg_proc",
            "information_schema.role_column_grants",
            "information_schema.triggers",
        ):
            with self.subTest(catalog=catalog):
                self.assertIn(catalog, self.sql)

    def test_roles_and_sensitive_columns_are_checked_without_values(self):
        self.assertIn("anon", self.sql)
        self.assertIn("authenticated", self.sql)
        self.assertIn("service_role", self.sql)
        self.assertIn("token", self.sql)
        self.assertIn("email", self.sql)
        self.assertIn("has_table_privilege", self.sql)
        self.assertIn("has_function_privilege", self.sql)


if __name__ == "__main__":
    unittest.main()
