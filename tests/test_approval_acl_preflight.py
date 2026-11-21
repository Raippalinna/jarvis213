"""Key-free regression tests: unsafe Approval Center grants must fail closed."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/security/check_approval_acl.py"
spec = importlib.util.spec_from_file_location("check_approval_acl", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def safe_rows():
    return [
        dict(table_name=name, rls_enabled=True, anon_select=False,
             anon_insert=False, anon_update=False, anon_delete=False,
             auth_insert=False, auth_update=False, auth_delete=False,
             anon_or_public_write_policies=0)
        for name in sorted(module.EXPECTED)
    ]


def test_safe_post_cutover_snapshot_passes():
    assert module.check_snapshot(safe_rows()) == []


def test_live_like_approval_exposure_is_blocked():
    rows = safe_rows()
    rows[0]["anon_insert"] = True
    rows[0]["anon_or_public_write_policies"] = 1
    rows[0]["auth_update"] = True
    errors = module.check_snapshot(rows)
    assert any("anon_table_grant" in item for item in errors)
    assert any("anon_or_public_write_policy" in item for item in errors)
    assert any("authenticated_write_grant" in item for item in errors)


def test_missing_table_or_permission_fails_closed():
    assert any("missing" in e for e in module.check_snapshot(safe_rows()[:-1]))
    rows = safe_rows()
    del rows[0]["rls_enabled"]
    assert any("missing_or_invalid_acl" in e for e in module.check_snapshot(rows))


def test_invalid_or_duplicate_snapshot_fails_closed():
    assert module.check_snapshot({}) == ["invalid_snapshot"]
    assert module.check_snapshot(safe_rows() + [safe_rows()[0]]) == ["unexpected_or_duplicate_table"]
    rows = safe_rows()
    rows[0]["anon_insert"] = "false"
    assert any("missing_or_invalid_acl" in e for e in module.check_snapshot(rows))


def test_rls_disabled_and_anon_memory_insert_are_rejected():
    rows = safe_rows()
    target = next(item for item in rows if item["table_name"] == "jarvis_memory")
    target["rls_enabled"] = False
    target["anon_insert"] = True
    errors = module.check_snapshot(rows)
    assert "jarvis_memory:rls_disabled" in errors
    assert "jarvis_memory:anon_table_grant" in errors


def test_preflight_sql_is_read_only_and_scoped():
    sql = (Path(__file__).resolve().parents[1] / "scripts/security/approval_acl_snapshot.sql").read_text(encoding="utf-8")
    # Check executable SQL lines, not comments; review SQL manually before use.
    code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--")).upper()
    for mutation in ("DROP ", "REVOKE ", "GRANT ", "ALTER ", "UPDATE ", "DELETE ", "INSERT ", "CREATE ", "TRUNCATE "):
        assert mutation not in code
    assert "PG_POLICIES" in code
    for name in module.EXPECTED:
        assert name in sql
