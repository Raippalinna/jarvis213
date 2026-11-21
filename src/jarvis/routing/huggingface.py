"""Explicit, single-provider HF profile. No network access during configuration.

This is an estimated per-request ceiling, not a provider-side billing limit or
an atomic monthly ledger. The shipped policy is deliberately incomplete/OFF.
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .tiers import NoEligibleRoute


HF_BASE_URL = "https://router.huggingface.co/v1"
HF_MODELS_URL = HF_BASE_URL + "/models"
POLICY_PATH = Path(__file__).resolve().parents[3] / "config" / "huggingface.json"
CATALOG_MAX_AGE_SECONDS = 86400
BUDGET_MAX_AGE_SECONDS = 3600


def selected() -> bool:
    return os.environ.get("JARVIS_PROVIDER", "default") == "huggingface"


def make_http_client():
    import httpx
    return httpx.AsyncClient(follow_redirects=False, timeout=30.0)


def _fresh(value, max_age: int) -> None:
    stamp = datetime.fromisoformat(value)
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if not 0 <= age <= max_age:
        raise ValueError("Expired or future timestamp")


def _number(value, *, positive=False) -> float:
    if type(value) not in (int, float):
        raise ValueError("A numeric value is required")
    number = float(value)
    if not math.isfinite(number) or (number <= 0 if positive else number < 0):
        raise ValueError("Invalid numeric value")
    return number


def _integer(value, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError("Invalid token limit")
    return value


def input_reservation(messages: list[dict]) -> int:
    """Conservative UTF-8 heuristic including role/framing, not exact tokenization."""
    return 256 + sum(
        32 + len(message["content"].encode("utf-8"))
        for message in messages
    )


def require_budget(catalog) -> None:
    try:
        _fresh(os.environ["JARVIS_HF_BUDGET_CHECKED_AT"], BUDGET_MAX_AGE_SECONDS)
        pct = float(os.environ["JARVIS_MONTH_SPEND_PCT"])
        if not math.isfinite(pct) or pct < 0:
            raise ValueError("Invalid budget")
    except (KeyError, ValueError, TypeError, OverflowError):
        raise NoEligibleRoute(
            "HF kräver budgetunderlag kontrollerat under den senaste timmen",
            "budget_unavailable",
        ) from None
    if pct >= float(catalog.budget.get("force_free_pct", 95)):
        raise NoEligibleRoute("Budgetveto: ingen HF-körning eller betald reservväg", "budget_blocked")


@dataclass(frozen=True)
class HFProfile:
    model: str
    tier: str
    max_input_tokens: int
    max_output_tokens: int
    max_estimated_cost_sek: float
    catalog_fetched_at: str

    def check(self, catalog, tier: str, messages: list[dict]) -> tuple[int, int]:
        if not selected() or os.environ.get("JARVIS_ENABLE_HUGGINGFACE") != "1":
            raise NoEligibleRoute("Hugging Face är inte aktiverat för detta uppdrag")
        if catalog.integration_status.get("huggingface") != "configured":
            raise NoEligibleRoute("Hugging Face är inte verifierat konfigurerat")
        if tier != self.tier:
            raise NoEligibleRoute("Uppdragets tier måste matcha den godkända HF-profilen")
        try:
            _fresh(self.catalog_fetched_at, CATALOG_MAX_AGE_SECONDS)
        except (ValueError, TypeError, OverflowError):
            raise NoEligibleRoute("HF-prisunderlaget har löpt ut") from None
        require_budget(catalog)
        estimated_in = input_reservation(messages)
        if estimated_in > self.max_input_tokens:
            raise NoEligibleRoute("Uppdraget överskrider HF-profilens inmatningsgräns", "data_blocked")
        cost = catalog.get("huggingface").estimate_cost_sek(
            estimated_in, self.max_output_tokens
        )
        if cost > self.max_estimated_cost_sek:
            raise NoEligibleRoute("HF-uppdraget överskrider uppskattat kostnadstak", "budget_blocked")
        return estimated_in, self.max_output_tokens


def require_profile(catalog) -> HFProfile:
    profile = getattr(catalog, "huggingface_profile", None)
    if catalog.integration_status.get("huggingface") != "configured" or profile is None:
        raise NoEligibleRoute(
            "HF är valt men avstängt, saknar nyckel eller har ofullständig konfiguration"
        )
    return profile


def configure_huggingface(catalog) -> None:
    """Never silently replace the requested provider with another route."""
    catalog.huggingface_profile = None
    catalog.integration_status["huggingface"] = "not_selected"
    if not selected():
        return
    # A failed explicit HF configuration must leave NO usable fallback chain.
    for config in catalog.tiers.values():
        config["chain"] = []
    catalog.integration_status["huggingface"] = "disabled"
    if os.environ.get("JARVIS_ENABLE_HUGGINGFACE") != "1":
        return
    try:
        policy = json.loads(Path(os.environ.get("JARVIS_HF_POLICY_PATH", POLICY_PATH)).read_text())
        if type(policy["schema_version"]) is not int or policy["schema_version"] != 1 or policy["enabled"] is not True:
            raise ValueError("Policy is not enabled")
        if policy["data_policy_approved"] is not True:
            raise ValueError("Data policy approval is missing")
        for field in ("approval_reference", "quality_evidence"):
            if not isinstance(policy[field], str) or not policy[field].strip():
                raise ValueError("Evidence is missing")
        model_id, provider_id, tier = policy["model_id"], policy["provider_id"], policy["tier"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", model_id):
            raise ValueError("Use an exact model ID")
        if not re.fullmatch(r"[a-z0-9-]+", provider_id) or provider_id in {
            "auto", "fastest", "cheapest", "preferred"
        }:
            raise ValueError("Pin one actual provider, not an automatic routing policy")
        if tier not in {"LOW", "MED", "HIGH"}:
            raise ValueError("HF cannot be registered as a FREE route")
        quality = _number(policy["quality_index"])
        if not float(catalog.tiers[tier]["quality_floor"]) <= quality <= 1:
            raise ValueError("Measured quality does not meet the existing tier floor")
        fx = _number(policy["usd_sek_assumption"], positive=True)
        max_input = _integer(policy["max_input_tokens"], 32768)
        max_output = _integer(policy["max_output_tokens"], 2000)
        cap = _number(policy["max_estimated_cost_sek"], positive=True)
        if cap > float(catalog.tiers[tier]["max_cost_per_call_sek"]):
            raise ValueError("HF cap cannot raise the existing tier ceiling")
        snapshot = json.loads(Path(os.environ["JARVIS_HF_CATALOG_PATH"]).read_text())
        _fresh(snapshot["fetched_at"], CATALOG_MAX_AGE_SECONDS)
        if snapshot["source_url"] != HF_MODELS_URL or snapshot["pricing_unit"] != "usd_per_1m_tokens":
            raise ValueError("Wrong catalog origin or units")
        matches = [m for m in snapshot["data"] if m.get("id") == model_id]
        if len(matches) != 1:
            raise ValueError("Model must appear exactly once")
        model = matches[0]
        if any(not isinstance(model["architecture"][key], list) or "text" not in model["architecture"][key]
               for key in ("input_modalities", "output_modalities")):
            raise ValueError("A text chat model is required")
        providers = [p for p in model["providers"] if p.get("provider") == provider_id]
        if len(providers) != 1 or providers[0]["status"] != "live":
            raise ValueError("The pinned provider must be live")
        item = providers[0]
        context = _integer(item["context_length"], 10000000)
        if max_input + max_output > context:
            raise ValueError("Token allowance exceeds the published context length")
        input_price = _number(item["pricing"]["input"])
        output_price = _number(item["pricing"]["output"])
        from .providers import ModelSpec, ProviderSpec
        pinned_model = f"{model_id}:{provider_id}"
        provider = ProviderSpec(
            key="huggingface", display_name="Hugging Face, explicit pinned route",
            base_url=HF_BASE_URL, api_key_env="HF_TOKEN",
            cost_per_1k_input_sek=input_price * fx / 1000,
            cost_per_1k_output_sek=output_price * fx / 1000,
            rate_limit_rpm=0, latency_p50_ms=0,
            # Conservative restriction, NOT a claim about provider training/retention.
            trains_on_data=True, sensitivity_max="internal",
            models=[ModelSpec(pinned_model, "user-evaluated", quality)],
            enabled_env="JARVIS_ENABLE_HUGGINGFACE",
        )
        catalog.providers[provider.key] = provider
        catalog.tiers[tier]["chain"] = [{"provider": provider.key, "model": pinned_model}]
        catalog.huggingface_profile = HFProfile(
            pinned_model, tier, max_input, max_output, cap, snapshot["fetched_at"]
        )
        catalog.integration_status["huggingface"] = (
            "configured" if provider.has_key() else "credential_missing"
        )
    except (KeyError, ValueError, TypeError, AttributeError, OSError, OverflowError):
        catalog.integration_status["huggingface"] = "configuration_blocked"
