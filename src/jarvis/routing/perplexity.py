"""Opt-in Perplexity Router adapter using a recent, explicitly fetched catalog."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path


ROUTER_BASE_URL = "https://api.perplexity.ai/router/v1"


def sek_per_1k(usd_per_1m: float, usd_sek: float) -> float:
    price, fx = float(usd_per_1m), float(usd_sek)
    if not math.isfinite(price) or price < 0 or not math.isfinite(fx) or fx <= 0:
        raise ValueError("Invalid price or exchange-rate assumption")
    return price * fx / 1000


def configure_router(catalog) -> None:
    """Never performs network I/O or silently substitutes a model."""
    if os.environ.get("JARVIS_ENABLE_PERPLEXITY") != "1":
        catalog.integration_status["perplexity_router"] = "disabled"
        return
    try:
        if os.environ.get("JARVIS_ROUTER_DATA_APPROVED") != "1":
            raise ValueError("Explicit data-policy approval is missing")
        model_id = os.environ["JARVIS_PERPLEXITY_MODEL"]
        tier = os.environ["JARVIS_ROUTER_TIER"].upper()
        if tier not in {"LOW", "MED", "HIGH"}:
            raise ValueError("Router cannot be registered as a free provider")
        quality = float(os.environ["JARVIS_ROUTER_QUALITY_INDEX"])
        if not math.isfinite(quality) or not 0 <= quality <= 1:
            raise ValueError("A measured quality index is required")
        fx = float(os.environ["JARVIS_ROUTER_USD_SEK"])
        snapshot = json.loads(Path(os.environ["JARVIS_ROUTER_MODELS_PATH"]).read_text())
        fetched = datetime.fromisoformat(snapshot["fetched_at"])
        age = (datetime.now(timezone.utc) - fetched).total_seconds()
        if not 0 <= age <= 86400 or snapshot["base_url"] != ROUTER_BASE_URL:
            raise ValueError("Model catalog is stale or has the wrong origin")
        matches = [m for m in snapshot["data"] if m.get("id") == model_id]
        if len(matches) != 1:
            raise ValueError("Requested model is not in the verified catalog")
        pricing = matches[0]["pricing"]
        if pricing["unit"] != "usd_per_1m_tokens":
            raise ValueError("Unknown pricing unit")
        from .providers import ModelSpec, ProviderSpec
        provider = ProviderSpec(
            key="perplexity_router", display_name="Perplexity Router (opt-in)",
            base_url=ROUTER_BASE_URL, api_key_env="PERPLEXITY_API_KEY",
            cost_per_1k_input_sek=sek_per_1k(pricing["input"], fx),
            cost_per_1k_output_sek=sek_per_1k(pricing["output"], fx),
            rate_limit_rpm=0, latency_p50_ms=0,
            # Conservative policy assumption, NOT a factual retention claim.
            trains_on_data=True, sensitivity_max="internal",
            models=[ModelSpec(model_id, "user-evaluated", quality)],
            enabled_env="JARVIS_ENABLE_PERPLEXITY",
        )
        catalog.providers[provider.key] = provider
        catalog.tiers[tier]["chain"].insert(0, {"provider": provider.key, "model": model_id})
        catalog.integration_status["perplexity_router"] = (
            "configured" if provider.has_key() else "credential_missing"
        )
    except (KeyError, ValueError, TypeError, OSError, OverflowError):
        # Do not print paths, payloads or exception strings from credential-backed work.
        catalog.integration_status["perplexity_router"] = "configuration_blocked"
