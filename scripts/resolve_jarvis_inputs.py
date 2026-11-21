"""Resolve GitHub workflow inputs without evaluating untrusted event text in Bash.

Output values are written through GITHUB_OUTPUT's file protocol using unpredictable
multiline delimiters. All untrusted values enter as environment values, never as
workflow expressions embedded in the run script.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4


ALLOWED_TIERS = frozenset({"FREE", "LOW", "MED", "HIGH"})
MAX_TASK_LENGTH = 8000


def _field(value: str, field: str, limit: int, *, multiline: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if "\x00" in value or "\r" in value or (not multiline and "\n" in value):
        raise ValueError(f"{field} contains forbidden control characters")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return value


def resolve(env: Mapping[str, str]) -> dict[str, str]:
    event = env.get("JARVIS_EVENT_NAME", "")
    if event == "repository_dispatch":
        task = env.get("JARVIS_PAYLOAD_TASK", "")
        tier = env.get("JARVIS_PAYLOAD_TIER", "")
        notion_page = env.get("JARVIS_PAYLOAD_NOTION", "")
        chat_id = env.get("JARVIS_PAYLOAD_CHAT_ID", "")
        origin_claim = env.get("JARVIS_PAYLOAD_ORIGIN", "")
        request_id = env.get("JARVIS_PAYLOAD_REQUEST_ID", "")
    elif env.get("JARVIS_CALL_TASK"):
        task = env.get("JARVIS_CALL_TASK", "")
        tier = env.get("JARVIS_CALL_TIER", "")
        notion_page = env.get("JARVIS_CALL_NOTION", "")
        chat_id = ""
        origin_claim = "workflow_call"
        request_id = ""
    else:
        task = env.get("JARVIS_DISPATCH_TASK", "")
        tier = env.get("JARVIS_DISPATCH_TIER", "")
        notion_page = env.get("JARVIS_DISPATCH_NOTION", "")
        chat_id = ""
        origin_claim = "workflow_dispatch"
        request_id = ""

    task = _field(task, "task", MAX_TASK_LENGTH, multiline=True)
    if not task:
        raise ValueError("task is required")
    tier = _field(tier, "tier", 4).upper() or "LOW"
    if tier not in ALLOWED_TIERS:
        raise ValueError("tier must be FREE, LOW, MED or HIGH")
    notion_page = _field(notion_page, "notion_page_id", 255)
    chat_id = _field(chat_id, "chat_id", 36)
    if chat_id:
        try:
            chat_id = str(UUID(chat_id))
        except ValueError as exc:
            raise ValueError("chat_id is invalid") from exc

    origin_claim = _field(origin_claim, "origin_claim", 40).lower() or "external_unverified"
    if origin_claim not in {"chatgpt", "perplexity", "comet", "workflow_call", "workflow_dispatch", "external_unverified"}:
        origin_claim = "external_unverified"
    request_id = _field(request_id, "request_id", 36)
    if request_id:
        try:
            request_id = str(UUID(request_id))
        except ValueError as exc:
            raise ValueError("request_id is invalid") from exc
    else:
        request_id = str(uuid4())

    # origin_claim is caller-supplied metadata, never an authenticated identity.
    return {
        "task": task,
        "tier": tier,
        "notion_page_id": notion_page,
        "chat_id": chat_id,
        "origin_claim": origin_claim,
        "request_id": request_id,
    }


def write_outputs(path: Path, values: Mapping[str, str]) -> None:
    with path.open("a", encoding="utf-8") as out:
        for key, value in values.items():
            if not key.isidentifier():
                raise ValueError("invalid output name")
            delimiter = f"JARVIS_{uuid4().hex}"
            while delimiter in value:
                delimiter = f"JARVIS_{uuid4().hex}"
            out.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


def main() -> int:
    try:
        values = resolve(os.environ)
        output = os.environ.get("GITHUB_OUTPUT")
        if not output:
            raise ValueError("GITHUB_OUTPUT is missing")
        write_outputs(Path(output), values)
    except (ValueError, OSError) as exc:
        print(f"Invalid Jarvis workflow input: {exc}", file=sys.stderr)
        return 2
    print(f"Jarvis input accepted: tier={values['tier']}; origin claim={values['origin_claim']}; request ID={values['request_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
