#!/usr/bin/env python3
"""JSON-only CLI for isolated research planning and explicitly public gh reads."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Support both `python scripts/jarvis_research.py` and `python -m scripts.jarvis_research`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.intelligence.github import ResearchRequest, search_public_repositories
from jarvis.intelligence.planner import plan_research


class InvalidArguments(Exception):
    pass


class JsonParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default error echoes arguments, potentially including secrets.
        raise InvalidArguments()

    def print_help(self, file=None) -> None:
        print(json.dumps({
            "state": "prepared", "help": self.format_help(),
            "network_requested": False, "agents_executed": 0,
        }, ensure_ascii=False), file=file)


def main(argv: list[str] | None = None) -> int:
    parser = JsonParser(description=__doc__)
    parser.add_argument("--task", default="", help="Local task; never sent to GitHub.")
    parser.add_argument("--domain", action="append", default=[], help="Explicit domain; repeatable.")
    parser.add_argument("--complexity", choices=("simple", "multi_domain"), default="simple")
    parser.add_argument("--max-sources", type=int, default=3)
    parser.add_argument("--max-calls", type=int, default=7)
    parser.add_argument("--public-query", default="", help="Only reviewed, sanitized public terms.")
    parser.add_argument("--sensitivity", choices=("unknown", "public", "internal", "confidential"),
                        default="unknown")
    parser.add_argument("--public-query-reviewed", action="store_true")
    parser.add_argument("--search", action="store_true", help="Request read-only GitHub search.")
    parser.add_argument("--cancelled", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.cancelled:
            output = {"state": "cancelled", "calls_used": 0}
        else:
            plan = plan_research(
                args.task, args.domain, complexity=args.complexity,
                max_sources=args.max_sources, max_calls=args.max_calls,
            )
            if plan["state"] == "blocked" or not args.search:
                output = plan
            else:
                output = search_public_repositories(ResearchRequest(
                    query=args.public_query, sensitivity=args.sensitivity,
                    public_query_reviewed=args.public_query_reviewed,
                    max_sources=args.max_sources, max_calls=args.max_calls,
                ))
                output["plan"] = plan
    except InvalidArguments:
        output = {"state": "blocked", "reasons": ["invalid_arguments"], "calls_used": 0}
    except KeyboardInterrupt:
        output = {"state": "cancelled", "calls_used": None,
                  "reasons": ["interrupted_call_count_unknown"]}
    print(json.dumps(output, ensure_ascii=False))
    return 130 if output["state"] == "cancelled" else (
        1 if output["state"] in {"blocked", "unavailable", "partial"} else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
