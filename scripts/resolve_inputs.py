"""Resolve GitHub event inputs without interpreting task text as shell code."""
import json
import os
import uuid
from pathlib import Path


def resolve(event_name, event, call_inputs):
    if event_name == "repository_dispatch":
        values = event.get("client_payload", {})
    elif call_inputs.get("task"):
        values = call_inputs
    else:
        values = event.get("inputs", {})
    task = values.get("task")
    tier = values.get("tier") or "LOW"
    page = values.get("notion_page_id") or ""
    provider = values.get("provider") or "default"
    if not isinstance(task, str) or not task.strip():
        raise ValueError("A non-empty task is required")
    if tier not in ("FREE", "LOW", "MED", "HIGH"):
        raise ValueError("Unknown tier")
    if not isinstance(page, str) or "\n" in page or "\r" in page:
        raise ValueError("Invalid Notion page ID")
    if provider not in ("default", "huggingface"):
        raise ValueError("Unknown provider profile")
    if provider == "huggingface":
        if event_name != "workflow_dispatch":
            raise ValueError("HF preparation permits manual workflow starts only")
        if tier == "FREE" or page:
            raise ValueError("HF cannot claim FREE pricing or deliver to a Notion page")
        if len(task.encode("utf-8")) > 6000:
            raise ValueError("HF task text is too large")
    return {"task": task, "tier": tier, "notion_page_id": page, "provider": provider}


def main():
    values = resolve(
        os.environ.get("GITHUB_EVENT_NAME", ""),
        json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()),
        json.loads(os.environ.get("CALL_INPUTS_JSON") or "{}"),
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        for key, value in values.items():
            delimiter = "jarvis_" + uuid.uuid4().hex
            while delimiter in value:
                delimiter = "jarvis_" + uuid.uuid4().hex
            output.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


if __name__ == "__main__":
    main()
