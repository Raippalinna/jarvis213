"""Förmånsbevakning: endast läsning, ingen inlösen eller kontoskrivning."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

MAX_BYTES = 500_000
TERMS = re.compile(r"promo|coupon|credit|kampanj|rabatt|gratis|free trial", re.I)

@dataclass(frozen=True)
class Source:
    url: str
    provider: str

@dataclass(frozen=True)
class Candidate:
    id: str
    provider: str
    source_url: str
    evidence: str
    observed_at: str
    status: str = "unverified"
    account_eligible: str = "unknown"
    realized_savings_sek: int = 0
    requires_approval: bool = True

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def validate_source(source, allowed_hosts):
    u = urlsplit(source.url)
    if (u.scheme != "https" or u.hostname not in allowed_hosts or
            u.username or u.password or u.port not in (None, 443) or u.fragment):
        raise ValueError("Källan måste vara HTTPS på en uttryckligen tillåten värd")
    if not source.provider.strip():
        raise ValueError("Leverantör saknas")

def scan(sources, fetch, allowed_hosts, *, cancelled=lambda: False, seen=()):
    """fetch(url, max_bytes) injiceras av värden; får endast läsa godkända källor.

    Innehållet behandlas som data, aldrig som instruktioner. Resultatet är
    kandidater, inte verifierade koder. Fel på en källa stoppar inte nästa.
    """
    known = set(seen)
    result = {"candidates": [], "errors": [], "cancelled": False}
    for source in sources:
        if cancelled():
            result["cancelled"] = True
            break
        try:
            validate_source(source, allowed_hosts)
            body = fetch(source.url, MAX_BYTES)
            if cancelled():
                result["cancelled"] = True
                break
            if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BYTES:
                raise ValueError("Ogiltigt eller för stort svar")
            parser = TextParser()
            parser.feed(body)
            for raw in parser.parts:
                text = " ".join(raw.split())
                if not TERMS.search(text):
                    continue
                evidence = text[:1000]
                key = sha256((source.url + "\n" + evidence).encode()).hexdigest()
                if key in known:
                    continue
                known.add(key)
                result["candidates"].append(asdict(Candidate(
                    key, source.provider, source.url, evidence,
                    datetime.now(timezone.utc).isoformat())))
        except Exception as exc:
            result["errors"].append({"provider": source.provider,
                                     "error_type": type(exc).__name__})
    return result
