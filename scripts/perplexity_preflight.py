#!/usr/bin/env python3
"""Read-only model-catalog check. Never calls a completion or purchases credits."""
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.routing.perplexity import ROUTER_BASE_URL, sek_per_1k  # noqa: E402


def fetch_catalog(key: str = "", *, proxy_credential: bool = False) -> dict:
    if not key and not proxy_credential:
        raise ValueError("credential_missing")
    url = f"{ROUTER_BASE_URL}/models"
    if proxy_credential:
        # The managed proxy's curl trust path was verified in this environment.
        # No credential value appears in arguments, output or files.
        result = subprocess.run(
            ["curl", "--silent", "--show-error", "--max-time", "20",
             "--write-out", "\n%{http_code}", url],
            capture_output=True, text=True, timeout=25,
        )
        if result.returncode:
            raise OSError("Proxy transport failed")
        body, status = result.stdout.rsplit("\n", 1)
        if not 200 <= int(status) < 300:
            raise urllib.error.HTTPError(url, int(status), "Catalog request failed", None, None)
        payload = json.loads(body)
    else:
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            payload = json.loads(response.read())
    models = []
    seen = set()
    for item in payload["data"]:
        model_id, pricing = item["id"], item["pricing"]
        if not isinstance(model_id, str) or not model_id or model_id in seen:
            raise ValueError("invalid_model_catalog")
        if pricing["unit"] != "usd_per_1m_tokens":
            raise ValueError("unsupported_pricing_unit")
        sek_per_1k(pricing["input"], 1)
        sek_per_1k(pricing["output"], 1)
        models.append({"id": model_id, "pricing": {
            "input": float(pricing["input"]), "output": float(pricing["output"]),
            "unit": "usd_per_1m_tokens",
        }})
        seen.add(model_id)
    if not models:
        raise ValueError("empty_model_catalog")
    return {"base_url": ROUTER_BASE_URL,
            "fetched_at": datetime.now(timezone.utc).isoformat(), "data": models}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--proxy-credential", action="store_true",
                        help="Use an explicitly approved credential-injecting HTTPS proxy")
    args = parser.parse_args()
    try:
        snapshot = fetch_catalog(os.environ.get("PERPLEXITY_API_KEY", ""),
                                 proxy_credential=args.proxy_credential)
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status": "http_error", "http_status": exc.code}))
        exc.close()
        return 1
    except urllib.error.URLError as exc:
        print(json.dumps({"status": "transport_error", "error_type": type(exc.reason).__name__}))
        return 1
    except Exception as exc:
        print(json.dumps({"status": "preflight_failed", "error_type": type(exc).__name__}))
        return 1
    if args.output:
        args.output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        print(json.dumps({"status": "catalog_verified", "model_count": len(snapshot["data"])}))
    else:
        print(json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
