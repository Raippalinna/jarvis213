#!/usr/bin/env python3
"""JARVIS Ω∞ OS v2 — Cloud Execution med Frugality Agent."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "src")

from langchain_core.messages import HumanMessage  # noqa: E402
from jarvis.core.supervisor import supervisor  # noqa: E402


def _post_to_notion_page(page_id: str, task: str, answer: str, meta: dict) -> str:
    import urllib.error
    import urllib.request

    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token or not page_id:
        return "notion: skipped"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = (
        f"Task: {task}\n"
        f"Tier: {meta.get('tier')}  Provider: {meta.get('provider')}/{meta.get('model')}\n"
        f"Kvalitet: {meta.get('quality')}  Kostnad: {meta.get('cost')} kr  Latens: {meta.get('latency')} ms\n"
    )
    body = header + "\n---\n\n" + answer
    chunks = [body[i : i + 1900] for i in range(0, len(body), 1900)] or [""]
    children = [{
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": f"JARVIS · {ts} · {task[:80]}"}}],
            "children": [
                {"object": "block", "type": "paragraph",
                 "paragraph": {"rich_text": [{"type": "text", "text": {"content": c}}]}}
                for c in chunks
            ],
        },
    }]
    req = urllib.request.Request(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        method="PATCH",
        data=json.dumps({"children": children}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"notion: ok {r.status}"
    except urllib.error.HTTPError as e:
        return f"notion: {e.code} {e.read().decode('utf-8','replace')[:200]}"
    except Exception as e:
        return f"notion: err {type(e).__name__}: {e}"


def _patch_chat_row(chat_id: str, payload: dict) -> str:
    """Rapportera framgång endast när exakt rätt chattrad återläses."""
    import urllib.error
    import urllib.request
    from uuid import UUID

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (chat_id and url and key):
        return "chat: skipped"
    try:
        normalized_id = str(UUID(chat_id))
    except (ValueError, TypeError, AttributeError):
        return "chat: invalid_id"
    req = urllib.request.Request(
        f"{url}/rest/v1/jarvis_chat?id=eq.{normalized_id}&select=id,status",
        method="PATCH",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=representation"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status != 200:
                return f"chat: unexpected_status {response.status}"
            rows = json.loads(response.read(65537))
            if not isinstance(rows, list) or len(rows) != 1:
                return "chat: write_unverified"
            row = rows[0]
            if not isinstance(row, dict) or row.get("id") != normalized_id:
                return "chat: write_unverified"
            if "status" in payload and row.get("status") != payload["status"]:
                return "chat: write_unverified"
            return "chat: ok 200 verified"
    except urllib.error.HTTPError as error:
        return f"chat: http_error {error.code}"
    except Exception as error:
        return f"chat: err {type(error).__name__}"


async def main() -> int:
    task = os.environ.get("TASK", "Hej Jarvis!")
    tier = os.environ.get("JARVIS_TIER", "LOW")
    notion_page_id = os.environ.get("NOTION_PAGE_ID", "").strip()
    chat_id = os.environ.get("CHAT_ID", "").strip()
    run_url = ""
    if os.environ.get("GITHUB_SERVER_URL") and os.environ.get("GITHUB_REPOSITORY") and os.environ.get("GITHUB_RUN_ID"):
        run_url = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    if chat_id:
        print(_patch_chat_row(chat_id, {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "run_url": run_url or None,
        }))

    print(f"Task: {task}")
    print(f"Tier: {tier}")
    print(f"Notion target: {notion_page_id or '(none)'}")
    # Minimlägg preflight-status (ingen värde-läcka)
    creds = {
        "comet": bool(os.environ.get("COMET_API_KEY")),
        "supabase": bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")),
        "notion": bool(os.environ.get("NOTION_TOKEN") and os.environ.get("NOTION_DB_BESLUTSLOGG")),
        "slack": bool(os.environ.get("SLACK_WEBHOOK_URL")),
    }
    print(f"Preflight: {creds}")
    print("-" * 60)

    try:
        state = await supervisor.chat(messages=[HumanMessage(content=task)], user_id="cloud")
    except Exception as e:  # noqa: BLE001
        if chat_id:
            print(_patch_chat_row(chat_id, {
                "status": "failed",
                "error": f"{type(e).__name__}: {str(e)[:300]}",
                "answered_at": datetime.now(timezone.utc).isoformat(),
            }))
        raise
    intent = state.get("intent")
    agents = state.get("active_agents", [])
    quality = state.get("quality_score", 0.0)
    fr = state.get("frugality", {})
    audit = fr.get("audit", {})
    answer = state["messages"][-1].content if state.get("messages") else ""

    print(f"Intent: {intent.category if intent else 'unknown'} "
          f"(conf {intent.confidence if intent else 0:.2f})  Agents: {agents}")
    print(f"Frugality: {fr.get('rationale', '—')}")
    if fr.get("handoff"):
        print(f"HANDOFF-FÖRSLAG: {fr['handoff']['display']} (spara ~{fr['handoff']['savings_sek']} kr)")
    for a in fr.get("alerts", []):
        print(f"  ! {a}")
    print(f"Quality: {quality} | Cost: {audit.get('actual_cost_sek', 0)} kr "
          f"| Latency: {audit.get('latency_ms', 0)} ms")
    print("-" * 60)
    print(answer)
    print("-" * 60)

    result = {
        "task": task,
        "tier": tier,
        "intent": intent.category if intent else "unknown",
        "confidence": intent.confidence if intent else 0.0,
        "agents": agents,
        "quality_score": quality,
        "frugality": fr,
        "answer": answer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    Path("result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    Path("result.md").write_text(
        f"# JARVIS Ω∞ OS — resultat\n\n"
        f"**Task:** {task}\n\n**Tier:** {tier}\n\n"
        f"**Provider:** {fr.get('provider')}/{fr.get('model')}\n\n"
        f"**Kvalitet:** {quality} · **Kostnad:** {audit.get('actual_cost_sek', 0)} kr · "
        f"**Latens:** {audit.get('latency_ms', 0)} ms\n\n---\n\n{answer}\n"
    )

    if chat_id:
        print(_patch_chat_row(chat_id, {
            "status": "answered" if answer else "failed",
            "answer": answer or None,
            "error": None if answer else "Tomt svar från supervisor",
            "provider": fr.get("provider"),
            "model": fr.get("model"),
            "quality": quality,
            "cost_sek": audit.get("actual_cost_sek", 0),
            "latency_ms": int(audit.get("latency_ms", 0) or 0),
            "answered_at": datetime.now(timezone.utc).isoformat(),
        }))

    if notion_page_id:
        print(_post_to_notion_page(notion_page_id, task, answer, {
            "tier": tier, "provider": fr.get("provider"), "model": fr.get("model"),
            "quality": quality, "cost": audit.get("actual_cost_sek", 0),
            "latency": audit.get("latency_ms", 0),
        }))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
