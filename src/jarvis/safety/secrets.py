"""Best-effort boundary redaction, not an exhaustive data-loss-prevention claim."""
from __future__ import annotations

import re


_PATTERNS = (
    re.compile(r"\b(?:hf_|sk-|pplx-|ghp_|github_pat_|ntn_|secret_|sb_secret_|xox[baprs]-)"
               r"[A-Za-z0-9_-]{12,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"(?i)\b(?:password|lösenord|api[_-]?key|api-nyckel|access_token|"
               r"service_role_key)\s*[:=]\s*[\"']?[^\"'\s,;]{4,}"),
)


def redact(text: str) -> str:
    result = str(text)
    for pattern in _PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def contains_secret(text: str) -> bool:
    return redact(text) != str(text)
