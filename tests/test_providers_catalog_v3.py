"""providers.yaml v3: katalogen laddar, alla kedjor pekar på definierade providers/modeller, budgetlarm 50/75/90."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.routing.providers import ProviderCatalog  # noqa: E402


def test_catalog_loads_and_chains_resolve():
    cat = ProviderCatalog()
    assert int(cat.raw["version"]) >= 3
    for tier, cfg in cat.tiers.items():
        assert cfg["chain"], tier
        for step in cfg["chain"]:
            prov = cat.get(step["provider"])
            assert prov is not None, f"{tier}: okänd provider {step['provider']}"
            assert prov.get_model(step["model"]) is not None, f"{tier}: okänd modell {step['model']}"


def test_free_tier_is_free_and_public_only():
    cat = ProviderCatalog()
    free = cat.tiers["FREE"]
    assert free["sensitivity_max"] == "public"
    first = cat.get(free["chain"][0]["provider"])
    assert first.cost_per_1k_input_sek == 0.0 and first.cost_per_1k_output_sek == 0.0


def test_budget_alerts_50_75_90():
    b = ProviderCatalog().budget
    assert (b["soft_alert_pct"], b["hard_alert_pct"], b["force_free_pct"]) == (50, 75, 90)
    assert b["credits_exhausted_mode"] == "FREE_ONLY"


def test_quality_floor_reachable_in_every_tier():
    cat = ProviderCatalog()
    for tier, cfg in cat.tiers.items():
        floor = float(cfg["quality_floor"])
        ok = any(cat.get(s["provider"]).get_model(s["model"]).quality_index >= floor for s in cfg["chain"])
        assert ok, f"{tier}: ingen modell når golvet {floor}"
