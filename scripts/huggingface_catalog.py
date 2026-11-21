"""Read the public HF catalog only. No token, completion, billing or dispatch."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://router.huggingface.co/v1/models"
MAX_BYTES = 2_000_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect_blocked")


def fetch_catalog(opener=None) -> dict:
    opener = opener or urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(
        URL, headers={"Accept": "application/json", "User-Agent": "Jarvis-public-catalog/1"}
    )
    with opener.open(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError("catalog_http_error")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("catalog_too_large")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list) or not payload["data"]:
        raise ValueError("catalog_schema_error")
    if not all(isinstance(item, dict) and isinstance(item.get("id"), str)
               for item in payload["data"]):
        raise ValueError("catalog_schema_error")
    return {
        "source_url": URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        # Documented units: https://huggingface.co/docs/inference-providers/en/hub-api
        "pricing_unit": "usd_per_1m_tokens",
        "data": payload["data"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        snapshot = fetch_catalog()
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError, TypeError, urllib.error.URLError):
        print(json.dumps({"status": "catalog_unavailable", "completion_requests": 0}))
        return 1
    print(json.dumps({
        "status": "public_catalog_saved", "model_count": len(snapshot["data"]),
        "completion_requests": 0, "inference_tested": False,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
