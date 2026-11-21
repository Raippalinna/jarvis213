"""Aviseringskanaler för Frugality-alerts och månadsrapport.

Två sinks som körs parallellt om nyckel finns:
- Slack DM till Ricky (SLACK_WEBHOOK_URL eller SLACK_BOT_TOKEN + SLACK_USER_ID)
- Notion Beslutslogg-block (NOTION_TOKEN + NOTION_LOG_PAGE_ID)

Tystnad om inga nycklar är satta — Jarvis får inte krascha bara för att en
sink saknas.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List


def _post(url: str, data: Dict, headers: Dict[str, str], timeout: int = 12) -> str:
    if not url or not url.startswith("http"):
        return f"skipped (invalid url: {url[:30]!r})"
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return f"ok {r.status}"
    except urllib.error.HTTPError as e:
        return f"http {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
    except Exception as e:
        return f"err {type(e).__name__}: {e}"


def _slack_send(title: str, body: str) -> str:
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if webhook:
        return _post(webhook, {"text": f"*{title}*\n{body}"}, {})
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    user = os.environ.get("SLACK_USER_ID", "").strip()
    if token and user:
        return _post(
            "https://slack.com/api/chat.postMessage",
            {"channel": user, "text": f"*{title}*\n{body}"},
            {"Authorization": f"Bearer {token}"},
        )
    return "skipped (no Slack creds)"


_NOTION_ID_RE = re.compile(r"[0-9a-fA-F]{32}")


def normalize_notion_page_id(raw: str) -> str:
    """Plocka ut Notions 32-teckens sid-id ur id, bindestrecks-UUID eller URL.

    Notion svarar 400 invalid_request_url om värdet innehåller URL-rester,
    query-parametrar eller radbrytning. Returnerar tom sträng om inget id finns.
    """
    candidate = (raw or "").strip().replace("-", "")
    m = _NOTION_ID_RE.search(candidate)
    return m.group(0).lower() if m else ""


def _notion_append(title: str, body: str) -> str:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    raw_page_id = os.environ.get("NOTION_LOG_PAGE_ID", "").strip()
    if not (token and raw_page_id):
        return "skipped (no Notion creds)"
    page_id = normalize_notion_page_id(raw_page_id)
    if not page_id:
        return "skipped (NOTION_LOG_PAGE_ID saknar giltigt 32-teckens sid-id)"
    if not (token.startswith("ntn_") or token.startswith("secret_")):
        return "skipped (invalid Notion token format)"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = f"{title}\n\n{body}"
    chunks = [text[i : i + 1900] for i in range(0, len(text), 1900)] or [""]
    children = [
        {
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": f"JARVIS · {ts} · {title[:80]}"}}],
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": c}}]},
                    }
                    for c in chunks
                ],
            },
        }
    ]
    return _post(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        {"children": children},
        {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"},
    )


def notify_all(title: str, body: str) -> Dict[str, str]:
    """Skicka till alla konfigurerade sinks. Returnerar per-sink-status."""
    return {"slack": _slack_send(title, body), "notion": _notion_append(title, body)}


def format_alerts(alerts: List[str]) -> str:
    if not alerts:
        return ""
    return "\n".join(f"• {a}" for a in alerts)
