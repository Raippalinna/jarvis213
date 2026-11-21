"""Review-only SQL lockdown contract (never executes SQL)."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "docs/security/approval-center-rls-lockdown.review.sql").read_text(encoding="utf-8").lower()
TABLES = ("approval_decision", "approval_request", "approval_audit_log")


def test_script_is_explicitly_not_auto_deployed():
    assert "review only" in SQL
    assert "not a supabase migration" in SQL
    assert SQL.count("begin;") == 1
    assert SQL.count("commit;") == 1
    assert "set local lock_timeout" in SQL
    assert "set local statement_timeout" in SQL
    assert "if not has_table_privilege('service_role'" in SQL


@pytest.mark.parametrize("table", TABLES)
def test_revokes_public_and_anon_and_authenticated(table):
    assert (
        f"revoke all privileges on table public.{table} from public, anon, authenticated;"
        in SQL
    )
    assert f"['approval_decision','approval_request','approval_audit_log']" in SQL


@pytest.mark.parametrize("permission", ["select", "insert", "update", "delete"])
def test_security_postcondition_checks_every_permission(permission):
    assert f"'{permission}'" in SQL


@pytest.mark.parametrize("policy,table", [
    ("jarvis_anon_tenant_insert", "approval_decision"),
    ("jarvis_anon_tenant_select", "approval_decision"),
    ("jarvis_anon_tenant_update", "approval_decision"),
    ("jarvis_backend_insert_pending", "approval_decision"),
    ("jarvis_backend_insert_request", "approval_request"),
    ("jarvis_backend_insert_audit", "approval_audit_log"),
])
def test_removes_unsafe_insert_and_anon_approval_policies(policy, table):
    assert f"drop policy if exists {policy} on public.{table};" in SQL


def test_no_unsafe_regrant_or_data_delete():
    assert "grant all on" not in SQL
    assert "grant update on" not in SQL
    assert "truncate " not in SQL
    assert "delete from public.approval_" not in SQL
