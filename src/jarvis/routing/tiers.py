"""TierRouter — väljer provider/modell utifrån tier + Frugality-regler."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
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


class NoEligibleRoute(RuntimeError):
    def __init__(self, reason: str, status: str = "route_blocked"):
        self.status = status
        super().__init__(reason)


def eligibility_reason(
    provider: ProviderSpec, model_id: str, tier_cfg: dict,
    sensitivity: Sensitivity, input_tokens: int, output_tokens: int,
    *, free_only: bool = False,
) -> str:
    """One predicate for both preflight selection and runtime fallback."""
    model = provider.get_model(model_id)
    if not model:
        return "okänd modell"
    if not provider.has_key():
        return "nyckel eller uttrycklig aktivering saknas"
    if sensitivity.rank() > Sensitivity(tier_cfg["sensitivity_max"]).rank():
        return "känslighet över tier-gräns"
    if sensitivity.rank() > Sensitivity(provider.sensitivity_max).rank():
        return "känslighet över leverantörsgräns"
    if provider.trains_on_data and sensitivity.rank() >= Sensitivity.CONFIDENTIAL.rank():
        return "stoppad av datapolicy"
    if model.quality_index is None or model.quality_index < float(tier_cfg["quality_floor"]):
        return "under konfigurerat modellgolv"
    estimate = provider.estimate_cost_sek(input_tokens, output_tokens)
    if not math.isfinite(estimate) or estimate < 0:
        return "ogiltigt kostnadsunderlag"
    if free_only and estimate > 0:
        return "betald fallback förbjuden i gratisläge"
    if estimate > float(tier_cfg["max_cost_per_call_sek"]):
        return "över uppskattat kostnadstak"
    return ""


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
        month_spend_pct: Optional[float] = None,
    ) -> RouteDecision:
        tiers = self.catalog.tiers

        if month_spend_pct is None or not math.isfinite(month_spend_pct) or month_spend_pct < 0:
            raise NoEligibleRoute("Tillförlitligt budgetunderlag saknas", "budget_unavailable")
        # A veto and an explicitly selected FREE tier cannot be escalated away.
        force_free_pct = float(self.catalog.budget.get("force_free_pct", 95))
        forced_free = month_spend_pct >= force_free_pct
        effective_tier = Tier.FREE if forced_free else tier
        free_only = forced_free or tier == Tier.FREE

        # 2. Sensitivity-eskalering
        while True:
            tier_cfg = tiers[effective_tier.value]
            allowed = Sensitivity(tier_cfg["sensitivity_max"])
            if sensitivity.rank() <= allowed.rank():
                break
            if free_only:
                raise NoEligibleRoute(
                    "Gratisläge och datapolicy saknar gemensam tillåten väg", "budget_blocked"
                )
            # eskalera
            order = [Tier.FREE, Tier.LOW, Tier.MED, Tier.HIGH]
            idx = order.index(effective_tier)
            if idx == len(order) - 1:
                break
            effective_tier = order[idx + 1]

        tier_cfg = tiers[effective_tier.value]
        chain = tier_cfg["chain"]

        notes: List[str] = []
        if forced_free:
            notes.append("BUDGET-VETO: månadsspend ≥ force_free_pct → tvingat FREE")
        if effective_tier != tier:
            notes.append(f"Tier-eskalering p.g.a. sensitivity: {tier.value} → {effective_tier.value}")

        for i, step in enumerate(chain):
            provider = self.catalog.get(step["provider"])
            reason = eligibility_reason(
                provider, step["model"], tier_cfg, sensitivity,
                est_input_tokens, est_output_tokens, free_only=free_only,
            )
            if reason:
                notes.append(f"skip {provider.key}: {reason}")
                continue
            model = provider.get_model(step["model"])
            est_cost = provider.estimate_cost_sek(est_input_tokens, est_output_tokens)

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

        raise NoEligibleRoute(
            "Ingen kandidat uppfyller policy: " + "; ".join(notes),
            "budget_blocked" if free_only else "route_blocked",
        )
