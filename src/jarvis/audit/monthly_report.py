"""Månatlig Frugality-audit — aggregerar `jarvis_memory` metadata.

Hämtar alla conversation-chunks från senaste 30 dagarna, räknar kostnad per tier
och per provider, och postar en kompakt rapport till Slack + Notion Beslutslogg.

Körs som eget cron-jobb (jarvis-cron-monthly-audit.yml).
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


def fetch_recent(days: int = 30) -> List[Dict[str, Any]]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase configuration missing")
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query = (
        f"{url}/rest/v1/jarvis_memory"
        f"?source=eq.conversation"
        f"&created_at=gte.{since}"
        f"&select=id,created_at,metadata,sensitivity"
        f"&limit=1000"
    )
    req = urllib.request.Request(query, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            rows = json.loads(r.read())
            if len(rows) >= 1000:
                raise RuntimeError("Audit result truncated; pagination required")
            return rows
    except Exception as exc:
        raise RuntimeError(f"Audit fetch failed: {type(exc).__name__}") from None


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
    avg_quality = round(quality_sum / quality_n, 2) if quality_n else None
    return {
        "period_days": 30,
        "total_calls": total,
        "coverage": "persisted_conversation_rows_only_not_all_provider_calls",
        "quality_kind": "format_heuristic_not_factual_verification",
        "cost_coverage_rows": sum(isinstance((r.get("metadata") or {}).get("actual_cost_sek"), (int, float)) for r in rows),
        "recorded_cost_sek": sum((r.get("metadata") or {}).get("actual_cost_sek", 0) or 0 for r in rows
                                 if isinstance((r.get("metadata") or {}).get("actual_cost_sek"), (int, float))),
        "avg_quality": avg_quality,
        "by_tier": dict(by_tier),
        "by_sensitivity": dict(by_sensitivity),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def post_slack(text: str) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url or not url.startswith("http"):
        return
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        raise RuntimeError(f"Slack delivery failed: {type(exc).__name__}") from None


def post_notion(title: str, body: str) -> None:
    token = os.environ.get("NOTION_TOKEN", "")
    page = os.environ.get("NOTION_LOG_PAGE_ID", "")
    if not token or not page:
        return
    children = [{
        "object": "block", "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title[:100]}}],
            "children": [{
                "object": "block", "type": "code",
                "code": {"language": "plain text",
                         "rich_text": [{"type": "text", "text": {"content": body[:1900]}}]},
            }],
        },
    }]
    req = urllib.request.Request(
        f"https://api.notion.com/v1/blocks/{page}/children",
        method="PATCH",
        data=json.dumps({"children": children}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28",
                 "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as exc:
        raise RuntimeError(f"Notion delivery failed: {type(exc).__name__}") from None


def main() -> int:
    rows = fetch_recent(30)
    report = build_report(rows)
    body = json.dumps(report, ensure_ascii=False, indent=2)
    print(body)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = (
        f"📊 *Jarvis Frugality-audit ({ts})*\n"
        f"• Anrop senaste 30d: *{report['total_calls']}*\n"
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
