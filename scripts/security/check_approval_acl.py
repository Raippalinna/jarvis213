#!/usr/bin/env python3
"""Offline fail-closed check of a catalog-only Supabase ACL snapshot.

Reads a local JSON snapshot produced by approval_acl_snapshot.sql.
Never connects to Supabase, loads secrets, or changes privileges.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXPECTED = frozenset({
    "approval_decision", "approval_request", "approval_audit_log", "jarvis_memory",
})
APPROVAL = EXPECTED - {"jarvis_memory"}
BOOLEAN_FIELDS = (
    "rls_enabled", "anon_select", "anon_insert", "anon_update", "anon_delete",
    "auth_insert", "auth_update", "auth_delete",
)


def check_snapshot(rows: object) -> list[str]:
    """Return non-sensitive failure codes, never raw database values."""
    if not isinstance(rows, list):
        return ["invalid_snapshot"]
    by_name: dict[str, dict] = {}
    failures: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("table_name"), str):
            return ["invalid_snapshot"]
        name = row["table_name"]
        if name not in EXPECTED or name in by_name:
            return ["unexpected_or_duplicate_table"]
        by_name[name] = row
    for name in sorted(EXPECTED):
        row = by_name.get(name)
        if row is None:
            failures.append(f"{name}:missing")
            continue
        if any(type(row.get(field)) is not bool for field in BOOLEAN_FIELDS):
            failures.append(f"{name}:missing_or_invalid_acl")
            continue
        n = row.get("anon_or_public_write_policies")
        if type(n) is not int or n < 0:
            failures.append(f"{name}:invalid_policy_count")
            continue
        if not row["rls_enabled"]:
            failures.append(f"{name}:rls_disabled")
        if any(row[field] for field in ("anon_select", "anon_insert", "anon_update", "anon_delete")):
            failures.append(f"{name}:anon_table_grant")
        if name in APPROVAL and any(row[field] for field in ("auth_insert", "auth_update", "auth_delete")):
            failures.append(f"{name}:authenticated_write_grant")
        if n:
            failures.append(f"{name}:anon_or_public_write_policy")
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"status": "invalid_usage", "usage": "check_approval_acl.py snapshot.json"}))
        return 2
    try:
        path = Path(argv[1])
        if path.stat().st_size > 65536:
            raise ValueError("oversized")
        rows = json.loads(path.read_text(encoding="utf-8"))
        failures = check_snapshot(rows)
    except (OSError, UnicodeError, ValueError):
        failures = ["invalid_snapshot"]
    print(json.dumps({
        "status": "pass" if not failures else "fail",
        "failing_checks": failures,
        "production_verified": False,
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
