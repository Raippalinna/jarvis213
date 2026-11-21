"""Resolve Actions input as data, never interpolated shell code."""
import json
import os
from pathlib import Path
from uuid import UUID, uuid4


def resolve(event, inputs, event_name):
    data = event.get("client_payload", {}) if event_name == "repository_dispatch" else (inputs or event.get("inputs", {}))
    task = data.get("task")
    tier = data.get("tier") or "LOW"
    page = data.get("notion_page_id") or ""
    if not isinstance(task, str) or not task.strip() or len(task) > 16000 or "\x00" in task:
        raise ValueError("task must contain 1–16000 characters")
    if tier not in ("FREE", "LOW", "MED", "HIGH"):
        raise ValueError("invalid tier")
    if not isinstance(page, str):
        raise ValueError("invalid Notion page")
    if page:
        page = str(UUID(page))
    return {"task": task, "tier": tier, "notion_page_id": page}


def encode_output(values):
    lines = []
    for key, value in values.items():
        delimiter = uuid4().hex
        while delimiter in value:
            delimiter = uuid4().hex
        lines.append(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
    return "".join(lines)


if __name__ == "__main__":
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    values = resolve(event, json.loads(os.environ.get("CALL_INPUTS_JSON", "{}")),
                     os.environ.get("GITHUB_EVENT_NAME", ""))
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(encode_output(values))
