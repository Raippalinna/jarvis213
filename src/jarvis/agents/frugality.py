"""Frugality Agent — snålhetsagenten.

Ansvar:
1. Pre-flight routing: välj billigaste ADEKVATA väg via TierRouter.
2. Manuell handoff: om M365 Copilot/Perplexity Pro/ChatGPT Go passar bättre
   OCH besparing >= tröskel OCH tid <= tröskel, skicka Slack/Notion-avisering
   istället för att autonomt anropa Comet.
3. Kvalitets-audit: efter kör, mät kvalitetsscore mot tier-floor. Under floor
   → auto-eskalera + AVISERA.
4. Månadsrapport: hur mycket sparades vs planerad kostnad.

Regler är DETERMINISTISK kod, inte LLM. Detta är krav från
[[projects/jarvis-ultimate-arkitektur]] — Approval-liknande logik får inte
delegeras till en LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..routing.providers import ProviderCatalog
from ..routing.tiers import RouteDecision, Sensitivity, Tier, TierRouter


HANDOFF_PATH = Path(__file__).parent.parent / "routing" / "handoff.yaml"


@dataclass
class HandoffSuggestion:
    channel_key: str
    display_name: str
    ux_note: str
    savings_sek: float
    quality_index: float


@dataclass
class FrugalityDecision:
    route: RouteDecision
    handoff: Optional[HandoffSuggestion] = None
    alerts: List[str] = field(default_factory=list)


class FrugalityAgent:
    def __init__(self, catalog: Optional[ProviderCatalog] = None):
        self.catalog = catalog or ProviderCatalog()
        self.router = TierRouter(self.catalog)
        with open(HANDOFF_PATH, encoding="utf-8") as fh:
            self.handoff_cfg = yaml.safe_load(fh)

    # -- Pre-flight -----------------------------------------------------------

    def pre_flight(
        self,
        intent: str,
        tier: Tier,
        est_input_tokens: int = 800,
        est_output_tokens: int = 800,
        sensitivity: Sensitivity = Sensitivity.INTERNAL,
        month_spend_pct: float = 0.0,
        allow_handoff: bool = True,
    ) -> FrugalityDecision:
        """Välj billigaste adekvata väg innan modellanrop."""
        route = self.router.choose(
            tier=tier,
            est_input_tokens=est_input_tokens,
            est_output_tokens=est_output_tokens,
            sensitivity=sensitivity,
            month_spend_pct=month_spend_pct,
        )

        handoff: Optional[HandoffSuggestion] = None
        alerts: List[str] = []
        if allow_handoff:
            handoff = self._maybe_handoff(intent, route)
            if handoff:
                alerts.append(
                    f"HANDOFF-FÖRSLAG: {handoff.display_name} — spara "
                    f"~{handoff.savings_sek:.1f} kr. {handoff.ux_note}"
                )

        # Budget-alert
        b = self.catalog.budget
        soft = float(b.get("soft_alert_pct", 50))
        hard = float(b.get("hard_alert_pct", 80))
        force = float(b.get("force_free_pct", 95))
        if month_spend_pct >= force:
            alerts.append(f"BUDGET-KRIS: månadsspend {month_spend_pct:.0f}% ≥ {force}% — tvingat FREE")
        elif month_spend_pct >= hard:
            alerts.append(f"BUDGET-VARNING: månadsspend {month_spend_pct:.0f}% ≥ {hard}%")
        elif month_spend_pct >= soft:
            alerts.append(f"BUDGET-info: månadsspend {month_spend_pct:.0f}% ≥ {soft}%")

        # Route notes → alerts (bara vid skip pga cap eller policy)
        for note in route.frugality_notes:
            if "BUDGET-VETO" in note or "sensitivity" in note or "tränar på data" in note:
                alerts.append(f"FRUGALITY: {note}")

        return FrugalityDecision(route=route, handoff=handoff, alerts=alerts)

    def _maybe_handoff(self, intent: str, route: RouteDecision) -> Optional[HandoffSuggestion]:
        thresholds = self.handoff_cfg.get("thresholds", {})
        min_sav = float(thresholds.get("min_savings_sek", 5.0))
        channels = self.handoff_cfg.get("channels", {})
        intent = (intent or "").lower()

        best: Optional[HandoffSuggestion] = None
        for key, ch in channels.items():
            if ch.get("reserved_for_human"):
                continue
            triggers = [t.lower() for t in ch.get("triggers", [])]
            if not any(t in intent for t in triggers):
                continue
            # Besparingen kan aldrig överstiga vad den automatiska vägen faktiskt
            # kostar. Utan detta föreslogs "spara ~15 kr" på ett 0,003-kr-anrop
            # och varje statuscheck skickade ett HANDOFF-larm.
            sav = min(float(ch.get("savings_per_task_sek", 0)), float(route.est_cost_sek or 0.0))
            if sav < min_sav:
                continue
            # Använd bara handoff om det ger MER kvalitet ELLER samma kvalitet + besparing
            if ch.get("quality_index", 0) + 0.01 < route.quality_index:
                continue
            cand = HandoffSuggestion(
                channel_key=key,
                display_name=ch["display_name"],
                ux_note=ch["ux_note"],
                savings_sek=sav,
                quality_index=float(ch["quality_index"]),
            )
            if best is None or cand.savings_sek > best.savings_sek:
                best = cand
        return best

    # -- Post-flight audit ----------------------------------------------------

    def audit(
        self,
        decision: FrugalityDecision,
        actual_quality: float,
        actual_cost_sek: float,
        latency_ms: int,
    ) -> Dict[str, Any]:
        """Kör efter modellanrop. Returnerar audit-rapport."""
        floor = float(self.catalog.tiers[decision.route.tier.value]["quality_floor"])
        under_floor = actual_quality < floor
        cost_delta = actual_cost_sek - decision.route.est_cost_sek

        report: Dict[str, Any] = {
            "tier": decision.route.tier.value,
            "provider": decision.route.provider.key,
            "model": decision.route.model_id,
            "quality_floor": floor,
            "actual_quality": actual_quality,
            "under_floor": under_floor,
            "est_cost_sek": round(decision.route.est_cost_sek, 4),
            "actual_cost_sek": round(actual_cost_sek, 4),
            "cost_delta_sek": round(cost_delta, 4),
            "latency_ms": latency_ms,
            "escalate": under_floor,
            "alerts": list(decision.alerts),
        }
        if under_floor:
            report["alerts"].append(
                f"KVALITETSAVVIKELSE: {actual_quality:.2f} < floor {floor:.2f} "
                f"(tier={decision.route.tier.value}) → eskalera"
            )
        return report
