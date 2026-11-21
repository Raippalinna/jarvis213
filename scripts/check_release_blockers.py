#!/usr/bin/env python3
"""Manuell, nyckelfri JARVIS-releasekontroll mot verifierade GitHub-ärendestatusar.

Ingen deployment, tokenrotation, databasskrivning eller modellkörning.
En grön ärendekontroll är INTE ett drift- eller säkerhetsintyg.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.request import HTTPRedirectHandler, Request, build_opener

EXPECTED_REPOSITORY = "rickyraippalinna/jarvis-omega-v2"
# Alla är uttryckligen blockerande säkerhets-/autentiseringsärenden.
P0_ISSUES = (13, 43, 52, 70)
API_ROOT = "https://api.github.com"


class Unverifiable(Exception):
    """GitHub-evidensen är otillgänglig eller otillräcklig."""


class _RejectRedirect(HTTPRedirectHandler):
    """Skicka aldrig GitHub Actions-token vidare via HTTP 30x."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_no_redirect(request: Request, timeout: int):
    return build_opener(_RejectRedirect()).open(request, timeout=timeout)


def issue_state(document: object, expected_number: int) -> str:
    """Returnera OPEN eller RESOLVED; neka alla oklara svar."""
    if not isinstance(document, dict):
        raise Unverifiable()
    if document.get("number") != expected_number or "pull_request" in document:
        raise Unverifiable()
    state = document.get("state")
    if state == "open":
        return "OPEN"
    if state == "closed" and document.get("state_reason") == "completed":
        return "RESOLVED"
    raise Unverifiable()


def read_issue(number: int, token: str, opener=_open_no_redirect) -> str:
    request = Request(
        f"{API_ROOT}/repos/{EXPECTED_REPOSITORY}/issues/{number}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jarvis-release-preflight",
        },
    )
    try:
        with opener(request, timeout=12) as response:
            if response.status != 200:
                raise Unverifiable()
            document = json.loads(response.read().decode("utf-8"))
        return issue_state(document, number)
    except Exception:
        # Skriv inte ut undantag, URL-headers, token eller provider-body.
        raise Unverifiable() from None


def release_preflight(repository: str, token: str, opener=_open_no_redirect) -> tuple[int, str]:
    if repository != EXPECTED_REPOSITORY or not token.strip():
        return 2, "EJ VERIFIERBART: fel repo eller saknad Actions-token."
    try:
        statuses = {number: read_issue(number, token, opener) for number in P0_ISSUES}
    except Unverifiable:
        return 2, "EJ VERIFIERBART: GitHub-svar saknas eller är otillräckligt."
    unresolved = [number for number, state in statuses.items() if state == "OPEN"]
    if unresolved:
        return 1, "BLOCKERAD RELEASE: öppna P0-ärenden " + ", ".join(f"#{n}" for n in unresolved)
    return (
        0,
        "P0-ÄRENDESKONTROLL GODKÄND. Inte ett tillstånd att merga, "
        "driftsätta eller köra autonomt. Kräver separat staging, "
        "Approval Center, verklig Auth/RLS-E2E och ägargranskning.",
    )


if __name__ == "__main__":
    code, message = release_preflight(
        os.environ.get("GITHUB_REPOSITORY", ""),
        os.environ.get("GITHUB_TOKEN", ""),
    )
    print(message)
    sys.exit(code)
