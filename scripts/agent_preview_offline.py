#!/usr/bin/env python3
"""Zero-network, zero-provider-cost preview of the main JARVIS agent DAG."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jarvis.core.agent_orchestrator import AgentOrchestrator, OrchestrationError  # noqa: E402


def main() -> int:
    goal = os.environ.get("JARVIS_PREVIEW_GOAL", "Improve the main Jarvis system")
    creative = os.environ.get("JARVIS_PREVIEW_CREATIVE", "").lower() == "true"
    notifications = os.environ.get("JARVIS_PREVIEW_NOTIFY", "").lower() == "true"
    try:
        orchestrator = AgentOrchestrator(
            goal, creative=creative, notifications=notifications,
            budget_sek="0", execution_enabled=False,
        )
        result = orchestrator.snapshot()
    except OrchestrationError:
        result = {
            "schema": "jarvis-agent-orchestration/v1",
            "status": "blocked",
            "reason": "invalid_preview_input",
            "execution_enabled": False,
            "production_verified": False,
        }
    output = ROOT / "agent-preview.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "agents": len(result.get("agents", {})),
        "execution_enabled": False,
        "production_verified": False,
        "output": output.name,
    }, sort_keys=True))
    return 0 if result["status"] == "planned" else 2


if __name__ == "__main__":
    raise SystemExit(main())
