"""Deterministisk källkontroll av modellsvar (grounding_check) utan nätverk.

Kontrollen mäter att varje numrerad punkt bär en 'Källa:'-rad – inte att källan
är sann. Saknad källa sätter ett tak på kvalitetspoängen under alla tier-golv.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.core import supervisor as sup  # noqa: E402


GROUNDED = (
    "1. **Flaskhals:** JARVIS Prime saknar verifierad driftkedja.\n"
    "Källa: Notion/Initiativ – JARVIS Prime\n\n"
    "2. **Handling:** Verifiera statuschecken i drift.\n"
    "Källa: wiki – jarvis-prime-systembygge\n\n"
    "3. **Ändrat sedan igår:** Inget registrerat sedan igår.\n"
    "Källa: inget registrerat – logga ändringar i Beslutsloggen.\n"
)
FABRICATED = (
    "1. **Flaskhals:** Resursbrist på utvecklare.\n\n"
    "2. **Handling:** Starta en rekryteringskampanj.\n"
    "Källa: Notion/Initiativ – JARVIS Prime\n\n"
    "3. **Ändrat:** Försening i materialleverans till Kungsgatan 37.\n"
)


def test_grounded_answer_all_items_sourced():
    g = sup.grounding_check(GROUNDED)
    assert g == {"checked": True, "items": 3, "sourced": 3, "unsourced": 0, "none_registered": 1}


def test_fabricated_answer_counts_unsourced_items():
    g = sup.grounding_check(FABRICATED)
    assert g["items"] == 3 and g["sourced"] == 1 and g["unsourced"] == 2


def test_unnumbered_answer_is_one_segment():
    assert sup.grounding_check("Allt lugnt.\nKälla: wiki – x")["unsourced"] == 0
    assert sup.grounding_check("Allt lugnt, inga ändringar.")["unsourced"] == 1


@pytest.mark.parametrize("body", ["", "   ", "(tomt svar från modellen)", "[JARVIS-fel] Alla kandidater misslyckades"])
def test_error_or_empty_is_not_checked(body):
    g = sup.grounding_check(body)
    assert g["checked"] is False and g["unsourced"] == 0


@pytest.mark.parametrize("line", ["Källa: x", "**Källa:** x", "- källa : x", "KÄLLA: Notion"])
def test_source_line_variants(line):
    assert sup.grounding_check(f"1. Punkt\n{line}")["sourced"] == 1


def test_inline_source_at_end_of_item_counts():
    """Driftkörning 41994995349: källan skrevs på samma rad som punkten."""
    body = (
        "1. Flaskhalsen är ÄTA-fångsten. Källa: Beslutslogg – BTF mappsystem 00–18.\n\n"
        "2. Påbörja styrmatrisen idag. Källa: Beslutslogg – BTF mappsystem 00–18.\n\n"
        "3. Inget registrerat i minnet. Källa: inget registrerat."
    )
    g = sup.grounding_check(body)
    assert g["items"] == 3 and g["sourced"] == 3 and g["unsourced"] == 0 and g["none_registered"] == 1


# --- integration genom execute() + reflect() ---------------------------------

def _state(role, task="Daglig statuscheck: (1) a, (2) b, (3) c. max 400 ord."):
    from langchain_core.messages import HumanMessage
    return {
        "messages": [HumanMessage(content=task)],
        "active_agents": [role],
        "memory_context": {"text": "### Aktivt kontrollrum (Notion)\n- JARVIS Prime", "summary": "notion=ja"},
        "frugality": {
            "tier": "LOW", "provider": "p1", "model": "m1",
            "est_input_tokens": 100, "est_output_tokens": 50, "rationale": "test",
        },
    }


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setattr(
        sup, "_memory_store", SimpleNamespace(enabled=False)
    )
    seen = {}

    class P:
        key, api_key_env, base_url = "p1", "P1_KEY", "http://p1"

        def estimate_cost_sek(self, i, o):
            return 0.01

    cat = SimpleNamespace(tiers={"LOW": {"chain": [{"provider": "p1", "model": "m1"}]}}, get=lambda k: P())
    monkeypatch.setattr(sup, "_catalog", cat)
    monkeypatch.setenv("P1_KEY", "k")

    def make(reply):
        class _Completions:
            async def create(self, **kw):
                seen["messages"] = kw["messages"]
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
                )

        class _Client:
            def __init__(self, *a, **k):
                self.chat = SimpleNamespace(completions=_Completions())

        monkeypatch.setattr(sup, "AsyncOpenAI", _Client)
        return seen

    return make


def test_strategist_gets_source_footer_and_fabrication_caps_quality(fake_llm):
    seen = fake_llm(FABRICATED)
    state = asyncio.run(sup.execute(_state("strategist")))
    assert sup.SOURCE_FOOTER in seen["messages"][1]["content"]
    # Uppgiftstexten i state är orörd (används av kvalitetsmått och minne).
    assert sup.SOURCE_FOOTER not in str(state["messages"][0].content)
    state = asyncio.run(sup.reflect(state))
    assert state["grounding"]["unsourced"] == 2 and state["grounding"]["quality_capped"] is True
    assert state["quality_score"] <= sup.UNGROUNDED_QUALITY_CAP


def test_grounded_answer_keeps_quality(fake_llm):
    fake_llm(GROUNDED)
    state = asyncio.run(sup.reflect(asyncio.run(sup.execute(_state("strategist")))))
    assert state["grounding"]["unsourced"] == 0 and "quality_capped" not in state["grounding"]
    assert state["quality_score"] > sup.UNGROUNDED_QUALITY_CAP


@pytest.mark.parametrize("role", ["casual", "coder"])
def test_casual_and_coder_are_not_source_checked(fake_llm, role):
    seen = fake_llm("Hej! Allt lugnt.")
    state = asyncio.run(sup.reflect(asyncio.run(sup.execute(_state(role, task="Hej, läget?")))))
    assert sup.SOURCE_FOOTER not in seen["messages"][1]["content"]
    assert state["grounding"] == {"required": False}
    assert state["quality_score"] > sup.UNGROUNDED_QUALITY_CAP


def test_cap_is_below_every_tier_floor():
    from jarvis.routing.providers import ProviderCatalog
    for name, cfg in ProviderCatalog().tiers.items():
        assert sup.UNGROUNDED_QUALITY_CAP < float(cfg["quality_floor"]), name
