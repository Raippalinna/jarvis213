"""Konservativ källnamnskontroll för JARVIS svar.

En angiven källtitel måste finnas i den minneskontext som faktiskt gavs till
modellen. Detta är en strängkontroll, inte verifiering av källans sakuppgifter.
Inga nätverksanrop eller databasåtgärder utförs.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict


_SOURCE_VALUE = re.compile(
    r"(?i)\bkälla[ \t*\x60_]*:[ \t*\x60_]*(?P<reference>[^\r\n]+)"
)
_SOURCE_SEPARATOR = re.compile(r"\s+[–—-]\s+")
# These are source types/sections, not specific records. Reject combinations
# too, otherwise e.g. "Notion/Initiativ" can match a context heading and pass.
_GENERIC_NAMES = {
    "notion", "wiki", "pgvector", "minne", "historik",
    "beslutslogg", "initiativ", "inkomst radar", "källa",
    "notion initiativ", "notion beslutslogg", "notion radar",
    "wiki beslut", "wiki arkitektoniska beslut",
}


def _normalized(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"[\u2010-\u2015_/\\-]", " ", text)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _source_title(reference: str) -> str:
    """Plocka ut en SPECIFIK posttitel ur t.ex. 'Notion/Initiativ – JARVIS Prime'."""
    clean = reference.strip(" \t*\x60_")
    pieces = _SOURCE_SEPARATOR.split(clean, maxsplit=1)
    candidate = pieces[1] if len(pieces) == 2 else clean
    candidate = candidate.strip(" \t*\x60_.,;:!")
    title = _normalized(candidate)
    if len(title) < 4 or title in _GENERIC_NAMES:
        return ""
    return title


def audit_source_titles(answer: str, context_text: str) -> Dict[str, Any]:
    """Matcha varje specificerad källtitel mot modellens faktiska källtext.

    'Källa: inget registrerat' godtas som deklarerad avsaknad av källa.
    Om ingen användbar kontext finns kan övriga titlar aldrig verifieras.
    Ett titelmatch ger INTE saklig verifiering av den citerade uppgiften.
    """
    context = f" {_normalized(context_text or '')} "
    cited = 0
    matched = 0
    unmatched = 0
    none_registered = 0
    for match in _SOURCE_VALUE.finditer(str(answer or "")):
        raw = match.group("reference").strip(" \t*\x60_")
        normalized = _normalized(raw)
        if normalized.startswith("inget registrerat"):
            none_registered += 1
            continue
        cited += 1
        title = _source_title(raw)
        if title and f" {title} " in context:
            matched += 1
        else:
            unmatched += 1
    result = {
        "title_references": cited,
        "matched_titles": matched,
        "unmatched_titles": unmatched,
        "declared_missing": none_registered,
        "title_check": "name_only_not_fact_verification",
    }
    if os.environ.get("JARVIS_STRICT_SOURCE_ALIGNMENT", "0") == "1":
        result.update(_strict_source_fields(str(answer or ""), str(context_text or "")))
    return result


def _strict_source_fields(answer: str, context_text: str) -> Dict[str, Any]:
    """Anpassa beläggskontroll till reflect():s befintliga räknare.

    I strikt läge betyder sourced/unsourced användbart referensstöd per punkt,
    inte enbart att texten innehåller Källa:. Formatmåtten bevaras separat.
    Ingen titelmatch är faktaverifiering. Fel ger aldrig rå feltext i metadata.
    """
    body = str(answer or "").strip()
    starts = [m.start() for m in re.finditer(r"(?m)^[^\w\r\n]{0,6}\d+[.)]", body)]
    segments = [body[a:b] for a, b in zip(starts, starts[1:] + [len(body)])] if starts else [body]
    format_pattern = re.compile(r"(?i)\bkälla[^\S\r\n]*:[^\S\r\n*`_]*[*`_]*[^\S\r\n]*(?=[^\s*`_])")
    format_sourced = sum(bool(format_pattern.search(seg)) for seg in segments)
    statuses = []
    supported = 0
    try:
        from .provenance import review_source_alignment
        if len(body) > 32000 or len(context_text) > 64000:
            statuses = ["input_limit_exceeded"]
        else:
            for seg in segments:
                status = review_source_alignment(seg, context_text).get("status", "check_failed")
                statuses.append(status)
                supported += bool(format_pattern.search(seg)) and status == "reviewable"
    except Exception:
        statuses = ["check_failed"]
        supported = 0
    blocked = len(segments) - supported
    return {
        "items": len(segments),
        "sourced": supported,
        "unsourced": blocked,
        "format_sourced": format_sourced,
        "format_unsourced": len(segments) - format_sourced,
        "source_alignment": {
            "strict": True,
            "blocked": blocked > 0,
            "statuses": statuses,
            "truth_verified": False,
        },
    }
