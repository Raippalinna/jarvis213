"""Kontrollera att JARVIS källhänvisningar pekar på titlar som faktiskt inlästs.

Testerna använder bara lokal text, inga secrets eller API-anrop.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.intelligence.source_references import audit_source_titles  # noqa: E402
from jarvis.core import supervisor as sup  # noqa: E402

CONTEXT = (
    "### Aktivt kontrollrum (Notion)\n"
    "### Initiativ (senaste 1)\n"
    "• JARVIS Prime — Status=aktiv\n"
    "### Beslutslogg (senaste 1)\n"
    "• BTF mappsystem 00–18 — Status=klart\n"
    "### Arkitektoniska beslut (wiki)\n"
    "### jarvis-prime-systembygge\n"
    "Versionsstyrda beslut om huvud-Jarvis."
)


@pytest.mark.parametrize("source", [
    "Källa: Notion/Initiativ – JARVIS Prime",
    "**Källa:** Notion/Initiativ – JARVIS Prime",
    "Punkt. Källa: Beslutslogg – BTF mappsystem 00–18.",
    "Källa: wiki – jarvis-prime-systembygge",
])
def test_real_source_titles_are_found(source):
    audit = audit_source_titles("1. Beslut. " + source, CONTEXT)
    assert audit["matched_titles"] == 1
    assert audit["unmatched_titles"] == 0
    assert audit["title_check"] == "name_only_not_fact_verification"


@pytest.mark.parametrize("source", [
    "Källa: Notion/Initiativ – Påhittad rekryteringskampanj",
    "Källa: wiki – ett-obefintligt-beslut",
    "Källa: Notion",
    "Källa: wiki",
    "Källa: x",
    "Källa: JARVIS Primes",  # inte en komplett tokengräns mot JARVIS Prime
])
def test_nonexistent_or_generic_titles_are_rejected(source):
    audit = audit_source_titles("1. Status. " + source, CONTEXT)
    assert audit["matched_titles"] == 0
    assert audit["unmatched_titles"] == 1


def test_no_memory_never_proves_a_positive_source():
    result = audit_source_titles("1. Klart. Källa: Notion/Initiativ – JARVIS Prime", "")
    assert result["matched_titles"] == 0 and result["unmatched_titles"] == 1


def test_none_registered_is_an_explicit_absence_not_a_verified_source():
    result = audit_source_titles(
        "1. Inget registrerat i minnet. Källa: inget registrerat – logga nästa körning.",
        "",
    )
    assert result["declared_missing"] == 1
    assert result["title_references"] == 0
    assert result["unmatched_titles"] == 0


def test_mixed_citations_count_each_title():
    reply = (
        "1. Verifierat i källtext. Källa: Notion/Initiativ – JARVIS Prime\n"
        "2. Saknas. Källa: wiki – fabricerat-underlag\n"
        "3. Inget registrerat. Källa: inget registrerat"
    )
    result = audit_source_titles(reply, CONTEXT)
    assert result["title_references"] == 2
    assert result["matched_titles"] == 1
    assert result["unmatched_titles"] == 1
    assert result["declared_missing"] == 1


def test_reflect_caps_quality_when_source_title_is_fabricated(monkeypatch):
    monkeypatch.setattr(sup, "_memory_store", type("Memory", (), {"enabled": False})())
    reply = (
        "1. Flaskhals: en ny påhittad leverans.\n"
        "Källa: Notion/Initiativ – Materialförseningen som aldrig loggades."
    )
    state = {
        "messages": [HumanMessage(content="Vad har ändrats?"), AIMessage(content=reply)],
        "memory_context": {"text": CONTEXT},
        "grounding": {"required": True},
    }
    result = asyncio.run(sup.reflect(state))
    assert result["grounding"]["unmatched_titles"] == 1
    assert result["grounding"]["quality_capped"] is True
    assert result["quality_score"] <= sup.UNGROUNDED_QUALITY_CAP


def test_reflect_preserves_quality_when_all_sources_are_in_context(monkeypatch):
    monkeypatch.setattr(sup, "_memory_store", type("Memory", (), {"enabled": False})())
    reply = (
        "1. Flaskhals: källhänvisning finns. Källa: Notion/Initiativ – JARVIS Prime\n"
        "2. Beslut finns. Källa: wiki – jarvis-prime-systembygge"
    )
    state = {
        "messages": [HumanMessage(content="Ge två punkter"), AIMessage(content=reply)],
        "memory_context": {"text": CONTEXT},
        "grounding": {"required": True},
    }
    result = asyncio.run(sup.reflect(state))
    assert result["grounding"]["unmatched_titles"] == 0
    assert result["grounding"]["matched_titles"] == 2
    assert "quality_capped" not in result["grounding"]
