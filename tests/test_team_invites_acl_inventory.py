"""Offline tests for the team_invites metadata-only inventory.

This file does not access Supabase or read any invitation rows/tokens.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "scripts/security/team_invites_acl_readonly.sql"
PLAN = ROOT / "docs/security/team-invites-cutover-20261117.md"


def _statements():
    sql = SQL.read_text(encoding="utf-8")
    cleaned = "\n".join(line for line in sql.splitlines()
                        if not line.lstrip().startswith("--"))
    return [p.strip() for p in cleaned.split(";") if p.strip()]


def test_inventory_is_six_read_only_catalog_queries():
    statements = _statements()
    assert len(statements) == 6
    for query in statements:
        assert query.lstrip().upper().startswith("SELECT ")
        assert not re.search(r"\\b(INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER|CREATE|REVOKE|GRANT|CALL|DO|COPY)\\b",
                             query, flags=re.IGNORECASE)


def test_inventory_only_reads_metadata():
    text = SQL.read_text(encoding="utf-8").lower()
    assert "from public.team_invites" not in text
    assert "select *" not in text
    assert "information_schema" in text
    assert "pg_policies" in text
    assert "pg_proc" in text
    assert "has_table_privilege" in text
    assert "has_function_privilege" in text


def test_cutover_has_explicit_release_guards():
    plan = PLAN.read_text(encoding="utf-8").lower()
    for expected in ("staging", "rollback", "auth", "token", "team", "godkännande", "ej driftsatt"):
        assert expected in plan
