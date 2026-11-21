#!/usr/bin/env python3
"""Correlate an isolated Comet dispatch with read-only HF identity checks."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import huggingface_preflight as hf

EXPECTED_REPOSITORY = "rickyraippalinna/jarvis-omega-v2"
EXPECTED_EVENT = "jarvis-connection-check"
UUID_V4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
MAX_EVENT_BYTES = 2 * 1024 * 1024


class InvalidCheck(RuntimeError):
    """Event failures are reported without user-controlled content."""


def validate_event(event_name: str, repository: str, event: object) -> str:
    if event_name != "repository_dispatch" or repository != EXPECTED_REPOSITORY:
        raise InvalidCheck()
    if not isinstance(event, dict) or event.get("action") != EXPECTED_EVENT:
        raise InvalidCheck()
    source = event.get("repository")
    if not isinstance(source, dict) or source.get("full_name") != EXPECTED_REPOSITORY:
        raise InvalidCheck()
    payload = event.get("client_payload")
    if not isinstance(payload, dict) or set(payload) != {"check_id"}:
        raise InvalidCheck()
    check_id = payload["check_id"]
    if not isinstance(check_id, str) or UUID_V4.fullmatch(check_id) is None:
        raise InvalidCheck()
    return check_id


def read_event() -> object:
    path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    with path.open("rb") as stream:
        raw = stream.read(MAX_EVENT_BYTES + 1)
    if len(raw) > MAX_EVENT_BYTES:
        raise InvalidCheck()
    return json.loads(raw)


def main() -> int:
    try:
        check_id = validate_event(
            os.environ.get("GITHUB_EVENT_NAME", ""),
            os.environ.get("GITHUB_REPOSITORY", ""),
            read_event(),
        )
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "completion_requests": 0}))
        return 130
    except Exception:
        print(json.dumps({"status": "invalid_connection_check", "completion_requests": 0}))
        return 1

    print(json.dumps({
        "event": EXPECTED_EVENT,
        "check_id": check_id,
        "normal_jarvis_run": False,
        "inference_requested": False,
    }))
    return hf.main()


if __name__ == "__main__":
    raise SystemExit(main())
