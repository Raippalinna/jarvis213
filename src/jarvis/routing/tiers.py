"""TierRouter — väljer provider/modell utifrån tier + Frugality-regler."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .providers import ProviderCatalog, ProviderSpec


class Tier(str, Enum):
    FREE = "FREE"
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"

    @classmethod
    def from_str(cls, s: str, default: "Tier" = None) -> "Tier":
        s = (s or "").upper().strip()
        for t in cls:
            if t.value == s:
                return t
        return default or cls.LOW


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"

    def rank(self) -> int:
        return {"public": 0, "internal": 1, "confidential": 2, "secret": 3}[self.value]


@dataclass
class RouteDecision:
    tier: Tier
    provider: ProviderSpec
    model_id: str
    quality_index: float
    est_cost_sek: float
    rationale: str
    fallback_index: int = 0        # 0 = primär, 1+ = användes fallback
    frugality_notes: List[str] = field(default_factory=list)


class TierRouter:
    """Bestämmer vilken provider/modell som ska anropas för en given task.

    Regler i ordning:
    1. Hoppa över fallback-poster där API-nyckel saknas.
    2. Om känslighet > tier.sensitivity_max → eskalera tier automatiskt.
    3. Om månadsbudget > force_free_pct → tvinga FREE (Frugality-veto).
    4. Estimera kostnad; om > max_cost_per_call_sek → hoppa till nästa i chain.
    5. Returnera första giltiga träffen med fallback-index och rationale.
    """

    def __init__(self, catalog: ProviderCatalog):
        self.catalog = catalog

    def choose(
        self,
        tier: Tier,
        est_input_tokens: int = 800,
        est_output_tokens: int = 800,
        sensitivity: Sensitivity = Sensitivity.INTERNAL,
        month_spend_pct: float = 0.0,
    ) -> RouteDecision:
        tiers = self.catalog.tiers

        # 3. Budget-veto
        force_free_pct = float(self.catalog.budget.get("force_free_pct", 95))
        forced_free = month_spend_pct >= force_free_pct
        effective_tier = Tier.FREE if forced_free else tier

        # 2. Sensitivity-eskalering
        while True:
            tier_cfg = tiers[effective_tier.value]
            allowed = Sensitivity(tier_cfg["sensitivity_max"])
            if sensitivity.rank() <= allowed.rank():
                break
            # eskalera
            order = [Tier.FREE, Tier.LOW, Tier.MED, Tier.HIGH]
            idx = order.index(effective_tier)
            if idx == len(order) - 1:
                break
            effective_tier = order[idx + 1]

        tier_cfg = tiers[effective_tier.value]
        chain = tier_cfg["chain"]
        floor = float(tier_cfg["quality_floor"])
        max_cost = float(tier_cfg["max_cost_per_call_sek"])

        notes: List[str] = []
        if forced_free:
            notes.append("BUDGET-VETO: månadsspend ≥ force_free_pct → tvingat FREE")
        if effective_tier != tier:
            notes.append(f"Tier-eskalering p.g.a. sensitivity: {tier.value} → {effective_tier.value}")

        for i, step in enumerate(chain):
            provider = self.catalog.get(step["provider"])
            model = provider.get_model(step["model"])
            if not model:
                continue
            if not provider.has_key():
                notes.append(f"skip {provider.key}: saknar {provider.api_key_env}")
                continue
            est_cost = provider.estimate_cost_sek(est_input_tokens, est_output_tokens)
            if est_cost > max_cost:
                notes.append(
                    f"skip {provider.key}/{model.id}: est.kostnad {est_cost:.3f} > cap {max_cost}"
                )
                continue
            if model.quality_index < floor:
                notes.append(
                    f"skip {provider.key}/{model.id}: quality {model.quality_index} < floor {floor}"
                )
                continue
            # Data-läckageskydd
            if provider.trains_on_data and sensitivity.rank() >= Sensitivity.CONFIDENTIAL.rank():
                notes.append(f"skip {provider.key}: tränar på data + sensitivity ≥ confidential")
                continue

            rationale = (
                f"Tier={effective_tier.value} chain[{i}]: {provider.display_name} · {model.id} · "
                f"q={model.quality_index} · ~{est_cost:.4f} kr"
            )
            return RouteDecision(
                tier=effective_tier,
                provider=provider,
                model_id=model.id,
                quality_index=model.quality_index,
                est_cost_sek=est_cost,
                rationale=rationale,
                fallback_index=i,
                frugality_notes=notes,
            )

        # Absolut sista utväg: comet_low/gpt-4o-mini oavsett
        provider = self.catalog.get("comet_low")
        model = provider.get_model("gpt-4o-mini")
        est_cost = provider.estimate_cost_sek(est_input_tokens, est_output_tokens) if model else 0
        notes.append("LAST-RESORT fallback: comet_low/gpt-4o-mini (alla chain-poster ogiltiga)")
        return RouteDecision(
            tier=effective_tier,
            provider=provider,
            model_id="gpt-4o-mini",
            quality_index=model.quality_index if model else 0.72,
            est_cost_sek=est_cost,
            rationale="LAST-RESORT",
            fallback_index=len(chain),
            frugality_notes=notes,
        )
