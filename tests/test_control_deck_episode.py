"""memory_episode-skrivning för JARVIS Control Deck: tyst utan nycklar, korrekt rad med nycklar."""
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load():
    # Importera jarvis_cloud utan att dra in LangGraph-supervisorn.
    import importlib.util
    fake = types.ModuleType("jarvis.core.supervisor"); fake.supervisor = None
    sys.modules.setdefault("jarvis", types.ModuleType("jarvis"))
    sys.modules.setdefault("jarvis.core", types.ModuleType("jarvis.core"))
    sys.modules["jarvis.core.supervisor"] = fake
    lc = types.ModuleType("langchain_core.messages"); lc.HumanMessage = object
    sys.modules.setdefault("langchain_core", types.ModuleType("langchain_core"))
    sys.modules["langchain_core.messages"] = lc
    spec = importlib.util.spec_from_file_location("jarvis_cloud", ROOT / "jarvis_cloud.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_skipped_without_keys(monkeypatch):
    mod = _load()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert mod._post_episode_to_supabase("t", "a", {}) == "episode: skipped"


def test_row_shape_and_truncation(monkeypatch):
    mod = _load()
    captured = {}

    class R:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        return R()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    out = mod._post_episode_to_supabase("x" * 500, "y" * 5000, {"tier": "LOW", "provider": "p", "quality": 1.0, "cost": 0})
    assert out == "episode: ok 201"
    assert captured["url"] == "https://example.supabase.co/rest/v1/memory_episode"
    b = captured["body"]
    assert b["episode_type"] == "jarvis_run"
    assert len(b["title"]) == 120 and len(b["summary"]) == 4000
    assert b["source_urls"] == ["https://github.com/o/r/actions/runs/123"]
    assert "tier:LOW" in b["source_systems"]
    assert captured["headers"]["prefer"] == "return=minimal"


def test_http_error_does_not_raise(monkeypatch):
    mod = _load()
    import urllib.error, urllib.request, io
    def boom(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 401, "x", {}, io.BytesIO(b"denied"))
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    assert mod._post_episode_to_supabase("t", "a", {}).startswith("episode: 401")
