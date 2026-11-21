"""Structural evidence checks, never an automatic determination of truth."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit

KINDS = {"primary", "secondary", "repository_metadata", "forum", "model_vote"}
STATUSES = {"unverified", "supported", "contradicted"}
REQUIRED = {
    "url", "fetched_at", "kind", "publisher", "origin", "actual_read",
    "claim", "status", "sensitivity",
}
TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src"}
ERROR_TEXT = re.compile(
    r"^\s*(?:error\s*[:\[]|traceback\b|\[jarvis-fel\]|"
    r"exception\s*:|access denied\b|http\s+[45]\d\d\b)", re.I,
)


def nonempty(value: object, limit: int = 2000) -> bool:
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= limit
            and not any(ord(c) < 32 for c in value if c not in "\n\t")
            and ERROR_TEXT.search(value) is None)


def valid_https_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 2000 or any(c.isspace() for c in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and parsed.port in {None, 443})
    except ValueError:
        return False


def resource_url_key(url: str) -> str:
    """Dedup key: fragments, trailing slashes, parameter order and tracking
    parameters do not create another source; resource-identifying query
    parameters (for example ``watch?v=<id>``) do."""
    parsed = urlsplit(url)
    params = sorted(
        (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.startswith("utm_") and key not in TRACKING_PARAMS
    )
    query = f"?{urlencode(params)}" if params else ""
    return f"{parsed.hostname.casefold()}{parsed.path.rstrip('/')}{query}"


def utc_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def assess_evidence(
    cards: object, *, now: datetime | None = None, max_age_days: int = 30,
) -> dict:
    """Eligibility for human/agent review, not a truth score.

    `supported` is an upstream assessment supplied by the caller. Origin labels,
    actual_read and claims cannot be authenticated by this structural policy.
    """
    now = datetime.now(timezone.utc) if now is None else now
    reasons: list[str] = []
    origins: set[str] = set()
    urls: set[str] = set()
    if (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
            or type(max_age_days) is not int or not 1 <= max_age_days <= 365):
        return {"status": "insufficient_evidence", "reasons": ["invalid_time_policy"],
                "independent_origins": 0}
    if not isinstance(cards, list) or not cards:
        return {"status": "insufficient_evidence", "reasons": ["evidence_required"],
                "independent_origins": 0}
    for index, card in enumerate(cards):
        prefix = f"card_{index}:"
        if not isinstance(card, dict) or not REQUIRED.issubset(card):
            reasons.append(prefix + "missing_fields")
            continue
        if (not all(nonempty(card.get(k)) for k in ("publisher", "origin", "claim"))
                or not valid_https_url(card.get("url"))
                or not isinstance(card.get("kind"), str) or card["kind"] not in KINDS
                or not isinstance(card.get("status"), str) or card["status"] not in STATUSES
                or type(card.get("actual_read")) is not bool
                or card.get("sensitivity") != "public"):
            reasons.append(prefix + "invalid_or_sensitive")
            continue
        fetched = utc_time(card["fetched_at"])
        if fetched is None:
            reasons.append(prefix + "timezone_aware_timestamp_required")
            continue
        if fetched > now:
            reasons.append(prefix + "future_timestamp")
            continue
        if now - fetched > timedelta(days=max_age_days):
            reasons.append(prefix + "stale")
            continue
        if card["status"] == "contradicted":
            reasons.append(prefix + "contradicted")
            continue
        if card["status"] != "supported" or card["actual_read"] is not True:
            reasons.append(prefix + "upstream_support_and_read_required")
            continue
        if card["kind"] in {"model_vote", "forum"}:
            reasons.append(prefix + "kind_cannot_independently_support")
            continue
        origin = " ".join(card["origin"].casefold().split())
        url_key = resource_url_key(card["url"])
        if origin in origins or url_key in urls:
            reasons.append(prefix + "duplicate_origin_or_url")
            continue
        origins.add(origin)
        urls.add(url_key)
    if len(origins) < 2:
        reasons.append("two_independent_upstream_supported_origins_required")
    return {
        "status": "eligible_for_review" if not reasons else "insufficient_evidence",
        "reasons": reasons, "independent_origins": len(origins),
        "truth_verified_by_module": False,
    }
