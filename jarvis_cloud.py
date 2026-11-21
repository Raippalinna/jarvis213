#!/usr/bin/env python3
"""JARVIS Ω∞ OS v2 — Cloud Execution med Frugality Agent."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from langchain_core.messages import HumanMessage  # noqa: E402
from jarvis.core.supervisor import supervisor  # noqa: E402
from jarvis.safety import guard  # noqa: E402
from jarvis.safety.secrets import contains_secret, redact  # noqa: E402
from jarvis.routing.huggingface import selected as huggingface_selected  # noqa: E402


def _execution_status(state: dict) -> str:
    if (state.get("approval") or {}).get("halted"):
        if state["approval"].get("persistence_status") == "failed":
            return "approval_persistence_failed"
        return "awaiting_approval"
    return state.get("frugality", {}).get("execution_status", "failed")


def _exit_code(status: str, delivery: str) -> int:
    if status == "failed":
        return 1
    if status == "awaiting_approval":
        return 2
    if status == "paused":
        return 4
    if status in {"budget_blocked", "budget_unavailable", "route_blocked"}:
        return 5
    if status == "data_blocked":
        return 6
    if status != "succeeded":
        return 1
    if not (delivery == "not_requested" or delivery.startswith("notion: verified ")):
        return 3
    return 0


def _post_to_notion_page(page_id: str, task: str, answer: str, meta: dict) -> str:
    import urllib.error
    import urllib.request

    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token or not page_id:
        return "notion: skipped"
    if contains_secret(task + "\n" + answer):
        return "notion: blocked_sensitive_content"
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
        guard.require_autonomy("notion_delivery")
        with urllib.request.urlopen(req, timeout=15) as r:
            receipt = json.loads(r.read())
        # A successful append response is not a verified saved briefing.
        blocks = receipt.get("results", [])
        if len(blocks) != 1 or not blocks[0].get("id"):
            return "notion: unverified_receipt"
        block_id = blocks[0]["id"]
        headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
        check = urllib.request.Request(
            f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100",
            headers=headers,
        )
        with urllib.request.urlopen(check, timeout=15) as r:
            saved = json.loads(r.read())
        saved_chunks = [
            "".join(part.get("plain_text", part.get("text", {}).get("content", ""))
                    for part in block.get("paragraph", {}).get("rich_text", []))
            for block in saved.get("results", [])
        ]
        if saved.get("has_more") or saved_chunks != chunks:
            return "notion: content_mismatch"
        return "notion: verified 200"
    except guard.SafetyStop as e:
        return f"notion: blocked {e.reason}"
    except urllib.error.HTTPError as e:
        return f"notion: http {e.code}"
    except Exception as e:
        return f"notion: err {type(e).__name__}"


async def main() -> int:
    task = os.environ.get("TASK", "Hej Jarvis!")
    tier = os.environ.get("JARVIS_TIER", "LOW")
    notion_page_id = os.environ.get("NOTION_PAGE_ID", "").strip()

    print(f"Task: {redact(task)}")
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

    # GitHub run_id remains stable across reruns; run_attempt must not enter
    # the idempotency identity. Other callers can supply a stable internal ID.
    session_id = os.environ.get("JARVIS_SESSION_ID", "").strip()
    if not session_id and os.environ.get("GITHUB_RUN_ID"):
        session_id = "github:" + os.environ["GITHUB_RUN_ID"]
    state = await supervisor.chat(
        messages=[HumanMessage(content=task)], user_id="cloud", session_id=session_id
    )
    intent = state.get("intent")
    agents = state.get("active_agents", [])
    quality = state.get("quality_score", 0.0)
    fr = state.get("frugality", {})
    audit = fr.get("audit", {})
    answer = redact(state["messages"][-1].content) if state.get("messages") else ""
    status = _execution_status(state)
    delivery = "not_requested"
    # Never publish a provider failure or approval hold as a normal briefing.
    if notion_page_id and status == "succeeded" and not huggingface_selected():
        delivery = _post_to_notion_page(notion_page_id, task, answer, {
            "tier": tier, "provider": fr.get("provider"), "model": fr.get("model"),
            "quality": quality, "cost": audit.get("actual_cost_sek", 0),
            "latency": audit.get("latency_ms", 0),
        })
        print(delivery)

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
        "status": status,
        "delivery_status": delivery,
        "task": redact(task),
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
        f"**Status:** {status}\n\n**Leverans:** {delivery}\n\n"
        f"**Task:** {redact(task)}\n\n**Tier:** {tier}\n\n"
        f"**Provider:** {fr.get('provider')}/{fr.get('model')}\n\n"
        f"**Kvalitet:** {quality} · **Kostnad:** {audit.get('actual_cost_sek', 0)} kr · "
        f"**Latens:** {audit.get('latency_ms', 0)} ms\n\n---\n\n{answer}\n"
    )

    return _exit_code(status, delivery)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
