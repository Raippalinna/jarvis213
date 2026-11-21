"""Tysta integrationstester med beroendedubblar; inga externa anrop."""
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.memory import context


class Hit:
    def __init__(self, source, content):
        self.source, self.content = source, content
        self.metadata = {"verified": True}
    def to_context_line(self):
        return self.content


@pytest.fixture
def configure(monkeypatch):
    def setup(rows=(), enabled=True, probe="ok", brief="", wiki=""):
        class Store:
            def __init__(self): self.enabled = enabled
            def key_role(self): return "service_role"
            def probe(self): return probe
            def search(self, **kw): return list(rows)
            def recent(self, **kw): return list(rows)
        class Room:
            enabled = True
            def brief(self, *a, **kw): return brief
            def recent_log(self, *a, **kw): raise AssertionError("Genererade loggar får inte hämtas")
        class Wiki:
            enabled = True
            def brief(self, *a, **kw): return wiki
        monkeypatch.setattr(context, "MemoryStore", Store)
        monkeypatch.setattr(context, "NotionControlRoom", Room)
        monkeypatch.setattr(context, "WikiReader", Wiki)
        monkeypatch.setenv("NOTION_DB_INITIATIV", "test-db")
        monkeypatch.setenv("NOTION_LOG_PAGE_ID", "test-log")
    return setup


@pytest.mark.parametrize("body", [None, "", " \n", "[JARVIS-fel] fel", "  [JARVIS-fel] fel", "(tomt svar från modellen)", "  (tomt svar från modellen)\n", "Q: Status?\nA: Påhitt"])
def test_invalid_rows_filtered_in_both_paths(configure, body):
    configure([Hit("legacy", body)])
    bundle = context.build_context("Status?")
    assert bundle.text == ""
    assert bundle.hits_vector == bundle.hits_recent == 0
    assert bundle.diagnostics["filtered_vector"] == 1
    assert bundle.diagnostics["filtered_recent"] == 1


@pytest.mark.parametrize("source", ["conversation", " CONVERSATION ", "Conversation"])
def test_self_claimed_verification_does_not_bypass_filter(configure, source):
    configure([Hit(source, "Påhittad säkerhetsåtgärd")])
    assert "Påhittad" not in context.build_context("Status?").text


def test_valid_sources_preserved_with_actual_counts(configure):
    rows = [Hit("manual", "Dokumentkälla"), Hit("conversation", "Påhitt")]
    configure(rows, brief="Initiativpost", wiki="### Beslut")
    bundle = context.build_context("Status?")
    assert "Dokumentkälla" in bundle.text and "Initiativpost" in bundle.text
    assert "### Beslut" in bundle.text and "Påhitt" not in bundle.text
    assert bundle.hits_vector == bundle.hits_recent == bundle.hits_wiki == 1
    assert bundle.hits_log == 0 and bundle.notion_used
    assert "notion_log" not in bundle.sources_used
    assert "återläsning=" in bundle.summary()
    assert rows[1].content == "Påhitt"


@pytest.mark.parametrize("probe", ["permission denied", "error 401"])
def test_unreadable_store_is_not_reported_healthy(configure, probe):
    configure(probe=probe)
    bundle = context.build_context("Status?")
    assert bundle.text == "" and probe in bundle.summary()


def test_disabled_store(configure):
    configure(enabled=False)
    assert context.build_context("Status?").diagnostics["store_probe"] == "disabled"


@pytest.mark.parametrize("cap", [0, 1, 9, 20, 4000])
def test_character_cap(configure, cap):
    configure([Hit("manual", "Källa" * 100)])
    assert len(context.build_context("Status?", max_chars=cap).text) <= cap
