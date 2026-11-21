#!/usr/bin/env python3
"""Nyckelfri läskontroll av Jarvis Comet-modeller mot CometAPI:s publika katalog."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.routing.providers import ProviderCatalog  # noqa: E402


CATALOG_URL = "https://api.cometapi.com/api/models"


def check_catalog(payload: dict, catalog: ProviderCatalog) -> dict:
    if payload.get("success") is not True or not isinstance(payload.get("data"), list):
        raise ValueError("CometAPI returnerade inte en giltig publik modellkatalog.")
    total = payload.get("total")
    if isinstance(total, int) and len(payload["data"]) < total:
        raise ValueError("CometAPI:s modellkatalog är paginerad eller ofullständig.")
    published = {
        row.get("id") for row in payload["data"]
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    configured = {
        model.id
        for provider in catalog.providers.values()
        if provider.base_url == "https://api.cometapi.com/v1"
        for model in provider.models
    }
    used = {
        step["model"]
        for tier in catalog.tiers.values()
        for step in tier["chain"]
        if catalog.get(step["provider"]).base_url == "https://api.cometapi.com/v1"
    }
    unlisted = sorted((configured | used) - published)
    unlisted_active = sorted(used - published)
    return {
        "catalog_total": total,
        "configured_model_ids": sorted(configured),
        "model_ids_not_listed": unlisted,
        "active_model_ids_not_listed": unlisted_active,
        "status": "catalog_ok" if not unlisted_active else "catalog_warning",
        "scope": (
            "Publik modellista, inte API-nyckel, saldo eller inferens. "
            "Ett olistat alias kan ändå fungera; verifiera mot senaste riktiga körning."
        ),
    }


def main() -> int:
    try:
        request = Request(CATALOG_URL, headers={"Accept": "application/json"})
        with urlopen(request, timeout=12) as response:
            payload = json.load(response)
        result = check_catalog(payload, ProviderCatalog())
        result["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        # Kod 1 kräver granskning, inte slutsatsen att modellen är nere.
        return 0 if result["status"] == "catalog_ok" else 1
    except Exception as error:  # noqa: BLE001
        # Skriv inte råa nätverksfel eller upstream-svar: de kan innehålla URL-parametrar.
        print(json.dumps({"status": "unavailable", "error_type": type(error).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
