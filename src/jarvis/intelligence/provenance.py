"""Read-only source-reference alignment for JARVIS.

A lexical match is NOT evidence that a claim is true. The guard never executes
content, accesses the network, changes approvals, or writes to storage.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_ITEM = re.compile(r"(?m)^[^\w\r\n]{0,6}\d+[.)]")
_SOURCE = re.compile(r"(?i)\bkälla\s*:\s*([^\r\n]+)")
_NONE = re.compile(r"^inget\s+registrerat\b", re.I)
_PREFIX = re.compile(r"^(?:(?:notion\s*/\s*initiativ|notion|beslutslogg|wiki|github)\s*[-–—:/]+\s*)+", re.I)
_INVALID = {"okänd", "saknas", "ingen källa", "n/a", "unknown", "källa", "notion", "wiki"}


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[‐‑‒–—−]", "-", value)
    return " ".join(value.split())


def _extract_reference(value: str) -> str:
    # A source is defined by the text after 'Källa:' on the same physical line.
    # Only strip presentation punctuation, not meaningful punctuation inside IDs.
    value = value.strip().strip("*_` ")
    value = value.rstrip(" .;,)").strip("*_` ")
    value = _PREFIX.sub("", value).strip()
    return _norm(value)


def review_source_alignment(answer: object, context: object) -> dict[str, Any]:
    """Check whether cited identifiers occur in the retrieved context.

    `reviewable` means every non-empty citation has a lexical context match;
    it does not verify quotation, entailment, recency, authenticity or truth.
    `citation_mismatch` blocks quality elevation when strict mode is enabled.
    `insufficient_context` does not treat supplied references as verified.
    """
    empty = {"status": "not_applicable", "items": 0, "matched": 0,
             "unmatched": 0, "no_evidence": 0, "missing": 0,
             "truth_verified": False, "checks": []}
    if not isinstance(answer, str) or not answer.strip():
        return empty
    if not isinstance(context, str) or not context.strip():
        return {**empty, "status": "insufficient_context"}
    if len(answer) > 32000 or len(context) > 64000:
        return {**empty, "status": "citation_mismatch", "checks": ["input_limit_exceeded"]}

    starts = [m.start() for m in _ITEM.finditer(answer)]
    segments = [answer[a:b] for a, b in zip(starts, starts[1:] + [len(answer)])] if starts else [answer]
    normalized_context = _norm(context)
    counts = {"matched": 0, "unmatched": 0, "no_evidence": 0, "missing": 0}
    checks: list[str] = []
    for seg in segments:
        matches = list(_SOURCE.finditer(seg))
        if not matches:
            counts["missing"] += 1
            checks.append("missing")
            continue
        # A segment may carry several citations; every one must be valid.
        for match in matches:
            ref = _extract_reference(match.group(1))
            if _NONE.match(ref):
                counts["no_evidence"] += 1
                checks.append("no_evidence")
            elif len(ref) < 8 or ref in _INVALID:
                counts["unmatched"] += 1
                checks.append("ambiguous_reference")
            elif re.search(r"(?<!\w)" + re.escape(ref) + r"(?!\w)", normalized_context):
                counts["matched"] += 1
                checks.append("lexical_match")
            else:
                counts["unmatched"] += 1
                checks.append("reference_not_in_context")
    if counts["unmatched"] or counts["missing"]:
        status = "citation_mismatch"
    elif counts["no_evidence"]:
        status = "insufficient_context"
    else:
        status = "reviewable"
    return {"status": status, "items": len(segments), **counts,
            "truth_verified": False, "checks": checks}
