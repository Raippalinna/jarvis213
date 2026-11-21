#!/usr/bin/env python3
"""Offline fail-closed fleet readiness check; no network or external actions."""
import argparse
import json
from pathlib import Path

REQUIRED = ("code_review", "tests", "auth", "tenant_isolation", "secrets", "integrations", "rollback", "owner_approval")


def assess(document):
    """Only explicit boolean True evidence counts; claims and unknowns fail closed."""
    if not isinstance(document, dict) or not isinstance(document.get("agents"), list) or not document["agents"]:
        raise ValueError("A nonempty agents array is required")
    results = []
    seen = set()
    for item in document["agents"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError("Every agent requires a nonblank id")
        agent_id = item["id"]
        if agent_id in seen:
            raise ValueError("Duplicate agent id")
        seen.add(agent_id)
        checks = item.get("checks")
        if not isinstance(checks, dict):
            checks = {}
        missing = [key for key in REQUIRED if checks.get(key) is not True]
        results.append({"id": agent_id, "ready": not missing, "missing": missing})
    return {"schema_version": 1, "ready": all(item["ready"] for item in results),
            "scope": "self_reported_evidence_only_not_live_verification", "agents": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Local evidence JSON file")
    args = parser.parse_args(argv)
    try:
        report = assess(json.loads(args.input.read_text(encoding="utf-8")))
    except (OSError, ValueError, UnicodeError) as error:
        print(json.dumps({"ready": False, "error": type(error).__name__}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
