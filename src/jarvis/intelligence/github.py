"""Bounded public GitHub metadata reads through an already authenticated gh."""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

REPOSITORY = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/"
    r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}"
)
SHA = re.compile(r"[a-f0-9]{40}")
LICENSE = re.compile(r"[A-Za-z0-9.+-]{1,100}")
FALLBACK = {
    "recommendation": "manual_web",
    "executed": False,
    "reason": "Granska en publik fråga och sök manuellt i webbläsare; inga resultat har hämtats där.",
}


@dataclass(frozen=True)
class ResearchRequest:
    query: str = ""
    sensitivity: str = "unknown"
    public_query_reviewed: bool = False
    cancelled: bool = False
    max_sources: int = 3
    max_calls: int = 7
    timeout_seconds: int = 10


class ReadFailure(Exception):
    """Only allow-listed codes may leave the adapter."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _query_allowed(query: object) -> bool:
    # Natural-language search terms only, never options, URLs or query qualifiers.
    return (isinstance(query, str) and 2 <= len(query) <= 200
            and query[0].isalnum()
            and all(c.isalnum() or c in " ._-" for c in query))


def search_public_repositories(
    request: ResearchRequest,
    *,
    run: Callable | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> dict:
    """Return candidate metadata, never fetched repository code or learned facts."""
    result = {
        "state": "blocked", "candidates": [], "trace": [],
        "calls_used": 0, "agents_executed": 0, "models_called": 0,
    }
    if request.cancelled is True:
        result.update(state="cancelled", reasons=["cancelled"])
        return result
    if (request.sensitivity != "public" or request.public_query_reviewed is not True
            or request.cancelled is not False):
        result["reasons"] = ["explicit_reviewed_public_query_required"]
        return result
    if not _query_allowed(request.query):
        result["reasons"] = ["invalid_public_query"]
        return result
    if (type(request.max_sources) is not int or not 1 <= request.max_sources <= 3
            or type(request.max_calls) is not int or not 1 <= request.max_calls <= 7
            or type(request.timeout_seconds) is not int or not 1 <= request.timeout_seconds <= 10):
        result["reasons"] = ["invalid_budget"]
        return result
    runner = run or subprocess.run
    # Pin both gh search and gh api to public GitHub, regardless of GH_HOST.
    environment = dict(os.environ, GH_HOST="github.com", GH_PROMPT_DISABLED="1",
                       GH_PAGER="cat", GH_DEBUG="")

    def read(args: list[str], step: str, index: int | None = None) -> object:
        trace = {"step": step, "candidate_index": index}
        try:
            if is_cancelled is not None and is_cancelled():
                raise ReadFailure("cancelled")
            if result["calls_used"] >= request.max_calls:
                raise ReadFailure("budget_exhausted")
            result["calls_used"] += 1
            response = runner(
                args, shell=False, capture_output=True, text=True,
                timeout=request.timeout_seconds, check=False, env=environment,
            )
            if response.returncode != 0:
                raise ReadFailure("gh_error")
            if not isinstance(response.stdout, str) or len(response.stdout) > 1_000_000:
                raise ReadFailure("invalid_response")
            try:
                value = json.loads(response.stdout)
            except (ValueError, TypeError):
                raise ReadFailure("invalid_response") from None
        except FileNotFoundError:
            trace["outcome"] = "gh_missing"
            raise ReadFailure("gh_missing") from None
        except subprocess.TimeoutExpired:
            trace["outcome"] = "timeout"
            raise ReadFailure("timeout") from None
        except KeyboardInterrupt:
            trace["outcome"] = "cancelled"
            raise ReadFailure("cancelled") from None
        except ReadFailure as failure:
            trace["outcome"] = failure.code
            raise
        except (OSError, ValueError, UnicodeError):
            trace["outcome"] = "unavailable"
            raise ReadFailure("unavailable") from None
        else:
            trace["outcome"] = "success"
            return value
        finally:
            result["trace"].append(trace)

    def fail(code: str, state: str = "unavailable") -> dict:
        result.update(state="cancelled" if code == "cancelled" else state, reasons=[code])
        if code != "cancelled":
            result["fallback"] = dict(FALLBACK)
        return result

    try:
        rows = read([
            "gh", "search", "repos", "--visibility=public",
            f"--limit={request.max_sources}", "--json=fullName,isPrivate", "--", request.query,
        ], "search")
    except ReadFailure as failure:
        return fail(failure.code)
    if not isinstance(rows, list) or len(rows) > request.max_sources:
        return fail("invalid_search_response")
    if not rows:
        result.update(state="no_results", reasons=[])
        return result
    failures = []
    seen = set()
    for index, row in enumerate(rows):
        name = row.get("fullName") if isinstance(row, dict) else None
        if (not isinstance(name, str) or REPOSITORY.fullmatch(name) is None
                or row.get("isPrivate") is not False or name.casefold() in seen):
            failures.append("invalid_public_candidate")
            result["trace"].append({
                "step": "candidate_validation", "candidate_index": index,
                "outcome": "invalid_public_candidate",
            })
            continue
        seen.add(name.casefold())
        try:
            metadata = read([
                "gh", "api", "--hostname", "github.com", "--method", "GET", f"repos/{name}",
            ], "metadata", index)
            if (not isinstance(metadata, dict) or metadata.get("full_name") != name
                    or metadata.get("private") is not False
                    or metadata.get("visibility") != "public"
                    or type(metadata.get("archived")) is not bool):
                raise ReadFailure("invalid_public_metadata")
            license_info = metadata.get("license")
            license_id = license_info.get("spdx_id") if isinstance(license_info, dict) else None
            if license_info is not None and (
                not isinstance(license_id, str) or LICENSE.fullmatch(license_id) is None
            ):
                raise ReadFailure("invalid_license_metadata")
            commits = read([
                "gh", "api", "--hostname", "github.com", "--method", "GET",
                f"repos/{name}/commits?per_page=1",
            ], "pin", index)
            sha = commits[0].get("sha") if (
                isinstance(commits, list) and len(commits) == 1
                and isinstance(commits[0], dict)
            ) else None
            if not isinstance(sha, str) or SHA.fullmatch(sha) is None:
                raise ReadFailure("invalid_commit_pin")
        except ReadFailure as failure:
            if failure.code == "cancelled":
                return fail("cancelled")
            failures.append(failure.code)
            result["trace"].append({
                "step": "candidate_validation", "candidate_index": index, "outcome": failure.code,
            })
            continue
        result["candidates"].append({
            "repository": name, "url": f"https://github.com/{name}",
            "source_version": sha, "pinned_url": f"https://github.com/{name}/tree/{sha}",
            "archived": metadata["archived"], "license": license_id,
            "license_reviewed": False, "code_read": False, "safe_to_execute": None,
            "evidence": {
                "url": f"https://github.com/{name}",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "kind": "repository_metadata", "publisher": name.split("/")[0],
                "origin": f"github:{name.casefold()}", "actual_read": True,
                "claim": "Publik repositorymetadata och exakt commit-SHA har lästs; kod har inte lästs.",
                "status": "unverified", "sensitivity": "public",
            },
        })
    if failures:
        return fail("candidate_reads_incomplete", "partial")
    result.update(state="search_completed", reasons=[])
    return result
