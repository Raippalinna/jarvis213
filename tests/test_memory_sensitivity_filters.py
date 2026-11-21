"""Nyckelfria regressionstester för minnesfiltrering."""
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest

spec = importlib.util.spec_from_file_location(
    "memory_filter_test_store", Path(__file__).resolve().parents[1] / "src/jarvis/memory/store.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setattr(module.urllib.request, "urlopen", Mock(side_effect=AssertionError("Nätverk förbjudet")))
    return module.MemoryStore("https://fzmnqvmfilqizzftphbt.supabase.co", "sb_" + "secret_synthetic_test_only")


@pytest.mark.parametrize("values", [[], ["secret"], ["public", "secret"], ["unknown"], "public", [None]])
@pytest.mark.parametrize("direct", [False, True])
def test_denied_without_external_calls(store, values, direct):
    store.embed = Mock(side_effect=AssertionError("Embedding förbjuden"))
    store._post_rpc = Mock(side_effect=AssertionError("RPC förbjuden"))
    if direct:
        assert store._fulltext_only("test", 5, values, None) == []
    else:
        assert store.search("test", allowed_sensitivity=values) == []
    store.embed.assert_not_called()
    store._post_rpc.assert_not_called()
    module.urllib.request.urlopen.assert_not_called()


@pytest.mark.parametrize("embedding", [None, [0.1]])
def test_empty_source_denies(store, embedding):
    store.embed = Mock(return_value=embedding)
    assert store.search("test", filter_source=[]) == []
    assert store._fulltext_only("test", 5, None, []) == []
    store.embed.assert_not_called()
    module.urllib.request.urlopen.assert_not_called()


@pytest.mark.parametrize("values,expected", [(None, ["public", "internal", "confidential"]), (["public"], ["public"]), (["internal", "internal"], ["internal"])])
@pytest.mark.parametrize("embedding", [None, [0.1]])
def test_filters_both_paths(store, monkeypatch, values, expected, embedding):
    store.embed = Mock(return_value=embedding)
    store._post_rpc = Mock(return_value=[])
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"[]"
    network = Mock(return_value=response)
    monkeypatch.setattr(module.urllib.request, "urlopen", network)
    assert store.search("test", allowed_sensitivity=values) == []
    if embedding is None:
        params = parse_qs(urlsplit(network.call_args.args[0].full_url).query)
        assert params["sensitivity"] == ['in.(' + ','.join(json.dumps(v) for v in expected) + ')']
        store._post_rpc.assert_not_called()
    else:
        assert store._post_rpc.call_args.args[1]["filter_sensitivity"] == expected
        network.assert_not_called()


def test_source_cannot_inject_query_parameter(store, monkeypatch):
    source = 'a"b' + chr(92) + 'c&limit=999'
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"[]"
    network = Mock(return_value=response)
    monkeypatch.setattr(module.urllib.request, "urlopen", network)
    assert store._fulltext_only("test", 5, None, [source]) == []
    params = parse_qs(urlsplit(network.call_args.args[0].full_url).query)
    assert params["limit"] == ["5"]
    assert params["source"] == ["in.(" + json.dumps(source) + ")"]


@pytest.mark.parametrize("embedding", [None, [0.1]])
def test_failed_retrieval_returns_empty(store, embedding):
    store.embed = Mock(return_value=embedding)
    store._post_rpc = Mock(side_effect=RuntimeError("simulerat fel"))
    assert store.search("test") == []


@pytest.mark.parametrize("embedding", [None, [0.1]])
def test_successful_hit(store, monkeypatch, embedding):
    row = {"id": 1, "source": "test", "kind": "chunk", "content": "exempel"}
    store.embed = Mock(return_value=embedding)
    store._post_rpc = Mock(return_value=[row])
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps([row]).encode()
    monkeypatch.setattr(module.urllib.request, "urlopen", Mock(return_value=response))
    hits = store.search("test", allowed_sensitivity=["public"])
    assert len(hits) == 1
    assert hits[0].content == "exempel"


def test_blank_query_without_embedding(store):
    store.embed = Mock(side_effect=AssertionError("Embedding förbjuden"))
    assert store.search("  ") == []
    store.embed.assert_not_called()


def test_wrong_backend_host_rejects_before_embedding_or_network(monkeypatch):
    network = Mock(side_effect=AssertionError("Nätverk förbjudet"))
    monkeypatch.setattr(module.urllib.request, "urlopen", network)
    instance = module.MemoryStore("https://example.invalid", "sb_" + "secret_synthetic_test_only")
    instance.embed = Mock(side_effect=AssertionError("Embedding förbjuden"))
    assert instance.search("test") == []
    assert instance.upsert("text", source="test") is None
    instance.embed.assert_not_called()
    network.assert_not_called()
