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


async def main() -> int:
    task = os.environ.get("TASK", "Hej Jarvis!")
    tier = os.environ.get("JARVIS_TIER", "LOW")
    notion_page_id = os.environ.get("NOTION_PAGE_ID", "").strip()

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

    state = await supervisor.chat(messages=[HumanMessage(content=task)], user_id="cloud")
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

    if notion_page_id:
        print(_post_to_notion_page(notion_page_id, task, answer, {
            "tier": tier, "provider": fr.get("provider"), "model": fr.get("model"),
            "quality": quality, "cost": audit.get("actual_cost_sek", 0),
            "latency": audit.get("latency_ms", 0),
        }))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
