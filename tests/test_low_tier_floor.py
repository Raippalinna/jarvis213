"""LOW-kedjans primärmodell måste klara LOW:s eget kvalitetsgolv.

Annars väljs samma modell ändå via LAST-RESORT, men utanför kedjans nyckel- och
kostnadskontroll och med rationale 'LAST-RESORT' i varje daglig statuscheck.
Beslut: Ricky 2026-11-05 (golv 0.75 → 0.70).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.routing.providers import ProviderCatalog  # noqa: E402
from jarvis.routing.tiers import Sensitivity, Tier, TierRouter  # noqa: E402


def test_low_primary_model_meets_low_floor():
    cat = ProviderCatalog()
    low = cat.tiers["LOW"]
    first = low["chain"][0]
    model = cat.get(first["provider"]).get_model(first["model"])
    assert model is not None
    assert model.quality_index >= float(low["quality_floor"])


def test_low_routes_through_chain_not_last_resort(monkeypatch):
    cat = ProviderCatalog()
    first = cat.tiers["LOW"]["chain"][0]
    monkeypatch.setenv(cat.get(first["provider"]).api_key_env, "test-key")
    decision = TierRouter(cat).choose(
        tier=Tier.LOW, sensitivity=Sensitivity.INTERNAL,
        est_input_tokens=1700, est_output_tokens=400,
    )
    assert decision.rationale != "LAST-RESORT"
    assert decision.rationale.startswith("Tier=LOW chain[0]")
    assert decision.model_id == first["model"]


def test_other_floors_unchanged():
    cat = ProviderCatalog()
    assert float(cat.tiers["MED"]["quality_floor"]) == 0.85
    assert float(cat.tiers["LOW"]["max_cost_per_call_sek"]) == 1.00
