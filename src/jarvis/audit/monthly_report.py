"""Scoped memory-record audit, not a billing ledger or a count of all API calls.

Failed and non-persisted turns are absent. A real usage ledger remains required.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from ..safety import guard
from ..memory.access import MemoryScope
from ..notify.sinks import _slack_send, _notion_append


def fetch_recent(days: int = 30) -> List[Dict[str, Any]]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("[audit] Supabase-creds saknas — hoppar över.")
        return []
    scope = MemoryScope.for_actor("cloud")
    if scope is None:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query = (
        f"{url}/rest/v1/jarvis_memory"
        f"?source=eq.conversation"
        f"&tenant_id=eq.{scope.tenant_id}&user_id=eq.{scope.user_id}"
        f"&created_at=gte.{since}"
        f"&select=id,created_at,metadata,sensitivity"
        f"&limit=1000"
    )
    req = urllib.request.Request(query, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as exc:
        print(f"[audit] Fetch-fel: {type(exc).__name__}")
        return []


def build_report(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_tier: Dict[str, int] = defaultdict(int)
    by_sensitivity: Dict[str, int] = defaultdict(int)
    total = len(rows)
    quality_sum = 0.0
    quality_n = 0
    for r in rows:
        meta = r.get("metadata") or {}
        tier = meta.get("tier") or "unknown"
        by_tier[tier] += 1
        by_sensitivity[r.get("sensitivity") or "unknown"] += 1
        q = meta.get("quality")
        if isinstance(q, (int, float)):
            quality_sum += float(q)
            quality_n += 1
    avg_quality = round(quality_sum / quality_n, 2) if quality_n else 0.0
    return {
        "period_days": 30,
        "total_calls": total,
        "coverage": "saved_memory_records_only_not_billing_or_all_calls",
        "avg_quality": avg_quality,
        "by_tier": dict(by_tier),
        "by_sensitivity": dict(by_sensitivity),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def post_slack(text: str) -> None:
    print("[audit] Slack:", _slack_send("Jarvis minnesaudit", text))


def post_notion(title: str, body: str) -> None:
    print("[audit] Notion:", _notion_append(title, body))


def main() -> int:
    try:
        guard.require_autonomy("monthly_audit")
    except guard.SafetyStop as exc:
        print(json.dumps({"status": "paused", "reason": exc.reason}))
        return 4
    if MemoryScope.for_actor("cloud") is None:
        print(json.dumps({"status": "memory_scope_missing"}))
        return 5
    rows = fetch_recent(30)
    report = build_report(rows)
    body = json.dumps(report, ensure_ascii=False, indent=2)
    print(body)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = (
        f"📊 *Jarvis Frugality-audit ({ts})*\n"
        f"• Sparade minnesposter senaste 30d: *{report['total_calls']}*\n"
        f"• Snittkvalitet: *{report['avg_quality']}*\n"
        f"• Per tier: `{report['by_tier']}`\n"
        f"• Per sensitivity: `{report['by_sensitivity']}`\n"
        f"Notion-postback + Jarvis-syntes följer separat."
    )
    post_slack(summary)
    post_notion(f"Frugality-audit {ts}", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
