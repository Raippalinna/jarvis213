"""Uppföljning på Codex-granskningen av minnesgrundningen (PR #5).

Testar utan nätverk:
- filtrering sker före resultatgränsen (överhämtning + tak),
- samtalsturer utesluts redan i databasfrågan för 'senaste',
- träffar som redan ligger i det semantiska blocket dubbleras inte,
- Notion-sinken plockar ut ett giltigt sid-id ur URL/UUID,
- ett tomt modellsvar avslutar inte kandidatkedjan.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.memory import context  # noqa: E402
from jarvis.notify import sinks  # noqa: E402


class Hit:
    def __init__(self, source, content, hit_id=None):
        self.source, self.content = source, content
        self.id = hit_id
        self.metadata = {}

    def to_context_line(self):
        return self.content


@pytest.fixture
def wire(monkeypatch):
    calls = {"search": [], "recent": []}

    def setup(search_rows=(), recent_rows=()):
        class Store:
            enabled = True

            def key_role(self):
                return "service_role"

            def probe(self):
                return "ok"

            def search(self, **kw):
                calls["search"].append(kw)
                return list(search_rows)

            def recent(self, **kw):
                calls["recent"].append(kw)
                return list(recent_rows)

        class Room:
            enabled = False

        class Wiki:
            enabled = False

        monkeypatch.setattr(context, "MemoryStore", Store)
        monkeypatch.setattr(context, "NotionControlRoom", Room)
        monkeypatch.setattr(context, "WikiReader", Wiki)
        return calls

    return setup


def test_filtering_happens_before_result_limit(wire):
    """Fem återcirkulerade samtalsträffar får inte tränga ut riktig källtext."""
    convo = [Hit("conversation", f"Q: Status?\nA: Påhitt {i}", hit_id=i) for i in range(1, 6)]
    real = [Hit("manual", "Dokumentkälla", hit_id=99)]
    calls = wire(search_rows=convo + real)
    bundle = context.build_context("Status?", vector_top_k=5)
    assert calls["search"][0]["match_count"] == 5 * context._OVERFETCH
    assert bundle.hits_vector == 1 and "Dokumentkälla" in bundle.text
    assert "Påhitt" not in bundle.text
    assert bundle.diagnostics["filtered_vector"] == 5


def test_vector_results_capped_at_top_k(wire):
    rows = [Hit("manual", f"Källa {i}", hit_id=i) for i in range(1, 10)]
    wire(search_rows=rows)
    bundle = context.build_context("Status?", vector_top_k=2)
    assert bundle.hits_vector == 2
    assert "Källa 1" in bundle.text and "Källa 2" in bundle.text and "Källa 3" not in bundle.text


def test_recent_excludes_conversation_in_query_and_overfetches(wire):
    calls = wire(recent_rows=[Hit("manual", "Senaste beslut", hit_id=7)])
    bundle = context.build_context("Status?", recent_k=5)
    kw = calls["recent"][0]
    assert set(kw["exclude_source"]) >= {"wiki", "conversation"}
    assert kw["limit"] == 5 * context._OVERFETCH
    assert bundle.hits_recent == 1 and "Senaste beslut" in bundle.text


def test_recent_hits_already_in_semantic_block_are_not_duplicated(wire):
    shared = Hit("manual", "Samma rad", hit_id=42)
    other = Hit("manual", "Annan rad", hit_id=43)
    wire(search_rows=[shared], recent_rows=[shared, other])
    bundle = context.build_context("Status?")
    assert bundle.hits_vector == 1 and bundle.hits_recent == 1
    assert bundle.text.count("Samma rad") == 1 and "Annan rad" in bundle.text


def test_rows_without_id_are_never_deduplicated_against_each_other(wire):
    wire(search_rows=[Hit("manual", "A")], recent_rows=[Hit("manual", "B")])
    bundle = context.build_context("Status?")
    assert bundle.hits_vector == 1 and bundle.hits_recent == 1


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("3ca66d43-c107-813b-90f3-daf5b5a42333", "3ca66d43c107813b90f3daf5b5a42333"),
        ("3CA66D43C107813B90F3DAF5B5A42333", "3ca66d43c107813b90f3daf5b5a42333"),
        (
            "https://www.notion.so/Control-Room-3ca66d43c107813b90f3daf5b5a42333?pvs=4",
            "3ca66d43c107813b90f3daf5b5a42333",
        ),
        ("  3ca66d43c107813b90f3daf5b5a42333\n", "3ca66d43c107813b90f3daf5b5a42333"),
        ("", ""),
        ("test-log", ""),
        ("3ca66d43c107813b90f3daf5b5a4233", ""),  # 31 tecken
    ],
)
def test_normalize_notion_page_id(raw, expected):
    assert sinks.normalize_notion_page_id(raw) == expected


def test_notion_sink_skips_cleanly_on_invalid_page_id(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "ntn_x")
    monkeypatch.setenv("NOTION_LOG_PAGE_ID", "not-a-page")
    monkeypatch.setattr(sinks, "_post", lambda *a, **k: pytest.fail("får inte anropa Notion"))
    assert "saknar giltigt" in sinks._notion_append("t", "b")


def test_notion_sink_posts_to_normalized_url(monkeypatch):
    seen = {}
    monkeypatch.setenv("NOTION_TOKEN", "ntn_x")
    monkeypatch.setenv("NOTION_LOG_PAGE_ID", "https://www.notion.so/x-3ca66d43c107813b90f3daf5b5a42333?pvs=4")
    monkeypatch.setattr(sinks, "_post", lambda url, data, headers, **k: seen.setdefault("url", url) and "ok 200")
    assert sinks._notion_append("t", "b") == "ok 200"
    assert seen["url"] == "https://api.notion.com/v1/blocks/3ca66d43c107813b90f3daf5b5a42333/children"


# --- Tomt svar får inte avsluta kandidatkedjan ------------------------------

def _fake_openai(script):
    """script: lista av 'empty' | 'text:<svar>' | 'raise' i anropsordning."""
    calls = []

    class _Completions:
        async def create(self, **kw):
            step = script[len(calls)]
            calls.append(kw["model"])
            if step == "raise":
                raise RuntimeError("provider down")
            content = None if step == "empty" else step.split(":", 1)[1]
            msg = SimpleNamespace(content=content)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=msg)],
                usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
            )

    class _Client:
        def __init__(self, *a, **k):
            self.chat = SimpleNamespace(completions=_Completions())

    return _Client, calls


def _state(tier="LOW", provider="comet_low", model="gpt-4o-mini"):
    from langchain_core.messages import HumanMessage
    return {
        "messages": [HumanMessage(content="Statuscheck")],
        "active_agents": ["strategist"],
        "memory_context": {},
        "frugality": {
            "tier": tier, "provider": provider, "model": model,
            "est_input_tokens": 100, "est_output_tokens": 50, "rationale": "test",
        },
    }


@pytest.fixture
def two_candidates(monkeypatch):
    from jarvis.core import supervisor

    class P:
        def __init__(self, key, env, base):
            self.key, self.api_key_env, self.base_url = key, env, base

        def estimate_cost_sek(self, i, o):
            return 0.5

    cat = SimpleNamespace(
        tiers={"LOW": {"chain": [
            {"provider": "p1", "model": "m1"},
            {"provider": "p2", "model": "m2"},
        ]}},
        get=lambda key: {"p1": P("p1", "P1_KEY", "http://p1"), "p2": P("p2", "P2_KEY", "http://p2")}[key],
    )
    monkeypatch.setattr(supervisor, "_catalog", cat)
    monkeypatch.setenv("P1_KEY", "k1")
    monkeypatch.setenv("P2_KEY", "k2")
    return supervisor


def test_empty_answer_falls_through_to_next_candidate(two_candidates, monkeypatch):
    sup = two_candidates
    Client, calls = _fake_openai(["empty", "text:Riktigt svar"])
    monkeypatch.setattr(sup, "AsyncOpenAI", Client)
    state = asyncio.run(sup.execute(_state(provider="p1", model="m1")))
    assert calls == ["m1", "m2"]
    assert state["messages"][-1].content == "Riktigt svar"
    assert state["frugality"]["provider"] == "p2" and state["frugality"]["model"] == "m2"
    assert any("tomt svar" in e for e in state["frugality"]["fallback_errors"])
    # Båda anropen nådde leverantören och debiteras.
    assert state["frugality"]["actual_cost_sek"] == pytest.approx(1.0)


def test_all_empty_keeps_known_placeholder(two_candidates, monkeypatch):
    sup = two_candidates
    Client, calls = _fake_openai(["empty", "empty"])
    monkeypatch.setattr(sup, "AsyncOpenAI", Client)
    state = asyncio.run(sup.execute(_state(provider="p1", model="m1")))
    assert calls == ["m1", "m2"]
    assert state["messages"][-1].content == "(tomt svar från modellen)"
    assert state["frugality"]["actual_cost_sek"] == pytest.approx(1.0)
    assert not sup._should_persist_turn("Statuscheck", state["messages"][-1].content)


def test_empty_then_exception_reports_error_not_placeholder(two_candidates, monkeypatch):
    sup = two_candidates
    Client, _ = _fake_openai(["empty", "raise"])
    monkeypatch.setattr(sup, "AsyncOpenAI", Client)
    state = asyncio.run(sup.execute(_state(provider="p1", model="m1")))
    assert state["messages"][-1].content.startswith("[JARVIS-fel]")
    assert "tomt svar" in state["messages"][-1].content and "provider down" in state["messages"][-1].content
