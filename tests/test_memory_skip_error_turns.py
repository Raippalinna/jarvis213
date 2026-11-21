"""Systemfel och tomma svar får inte sparas som samtalsminne.

Tysta tester utan nycklar: MemoryStore ersätts med en testdubbel.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from jarvis.core import supervisor  # noqa: E402


class _FakeStore:
    enabled = True

    def __init__(self, fail: bool = False):
        self.rows = []
        self.fail = fail

    def upsert(self, **row):
        if self.fail:
            raise RuntimeError("supabase nere")
        self.rows.append(row)
        return 1


def _state(user: str, answer: str) -> dict:
    return {
        "messages": [HumanMessage(content=user), AIMessage(content=answer)],
        "session_id": "s-test",
        "current_user_id": "u-test",
        "frugality": {"tier": "low"},
    }


def _run_reflect(monkeypatch, user: str, answer: str, store=None):
    store = store or _FakeStore()
    monkeypatch.setattr(supervisor, "_memory_store", store)
    asyncio.run(supervisor.reflect(_state(user, answer)))
    return store


def test_should_persist_normal_turn():
    assert supervisor._should_persist_turn("Vad är status?", "Inget registrerat i minnet.")


def test_should_not_persist_error_answer():
    assert not supervisor._should_persist_turn("Status?", "[JARVIS-fel] Alla 3 kandidater misslyckades")
    assert not supervisor._should_persist_turn("Status?", "   [JARVIS-fel] indrag")


def test_should_not_persist_empty_or_whitespace_answer():
    assert not supervisor._should_persist_turn("Status?", "")
    assert not supervisor._should_persist_turn("Status?", "   \n\t ")
    assert not supervisor._should_persist_turn("Status?", "(tomt svar från modellen)")


def test_should_not_persist_without_user_text():
    assert not supervisor._should_persist_turn("", "Ett riktigt svar")
    assert not supervisor._should_persist_turn("   ", "Ett riktigt svar")


def test_reflect_saves_normal_turn(monkeypatch):
    store = _run_reflect(monkeypatch, "Hur mår kassaflödet?", "Inget registrerat i minnet om kassaflödet.")
    assert len(store.rows) == 1
    assert store.rows[0]["source"] == "conversation"
    assert store.rows[0]["content"].startswith("Q: Hur mår kassaflödet?")


def test_reflect_skips_error_answer(monkeypatch):
    store = _run_reflect(monkeypatch, "Status?", "[JARVIS-fel] Alla kandidater misslyckades:\n- x")
    assert store.rows == []


def test_reflect_skips_empty_answer(monkeypatch):
    store = _run_reflect(monkeypatch, "Status?", "   ")
    assert store.rows == []


def test_reflect_skips_placeholder_answer(monkeypatch):
    store = _run_reflect(monkeypatch, "Status?", "(tomt svar från modellen)")
    assert store.rows == []


def test_reflect_survives_store_failure(monkeypatch):
    store = _run_reflect(monkeypatch, "Status?", "Riktigt svar", store=_FakeStore(fail=True))
    assert store.rows == []  # inget sparat, men inget undantag heller


def test_reflect_sets_quality_score_even_when_skipping(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(supervisor, "_memory_store", store)
    st = _state("Status?", "[JARVIS-fel] fel")
    asyncio.run(supervisor.reflect(st))
    assert "quality_score" in st
    assert store.rows == []
