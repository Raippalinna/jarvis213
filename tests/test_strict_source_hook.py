"""Isolerad test av strikt källkontroll och oförändrad reflect-funktion."""
import ast
import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def modules(monkeypatch):
    name = "_jarvis_strict_test"
    package = types.ModuleType(name)
    package.__path__ = [str(ROOT / "src/jarvis/intelligence")]
    monkeypatch.setitem(sys.modules, name, package)
    loaded = []
    for leaf in ("provenance", "source_references"):
        spec = importlib.util.spec_from_file_location(
            name + "." + leaf, ROOT / "src/jarvis/intelligence" / (leaf + ".py"))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        loaded.append(module)
    return loaded


@pytest.mark.parametrize("flag", [None, "0", "false", "TRUE", ""])
def test_disabled_preserves_old_contract(modules, monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("JARVIS_STRICT_SOURCE_ALIGNMENT", raising=False)
    else:
        monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", flag)
    result = modules[1].audit_source_titles("1. Saknas. Källa: inget registrerat", "JARVIS Prime")
    assert result == {"title_references": 0, "matched_titles": 0,
        "unmatched_titles": 0, "declared_missing": 1,
        "title_check": "name_only_not_fact_verification"}


@pytest.mark.parametrize("answer,context,blocked", [
    ("1. Förslag. Källa: JARVIS Prime", "JARVIS Prime", 0),
    ("1. Försening. Källa: inget registrerat", "JARVIS Prime", 1),
    ("1. Inget registrerat i minnet. Källa: inget registrerat", "JARVIS Prime", 1),
    ("1. Förslag. Källa: JARVIS Prime\n2. Försening. Källa: inget registrerat", "JARVIS Prime", 1),
    ("1. Fynd utan källa\n2. Saknas. Källa: inget registrerat", "JARVIS Prime", 2),
    ("1. Förslag. Källa: JARVIS Prime", "", 1),
    ("1. Fel. Källa: Påhittad leverans", "JARVIS Prime", 1),
    ("1. Förslag. Källa: JARVIS Prime\nKälla: Påhittad leverans", "JARVIS Prime", 1),
])
def test_strict_counts(modules, monkeypatch, answer, context, blocked):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    result = modules[1].audit_source_titles(answer, context)
    assert result["unsourced"] == blocked
    assert result["sourced"] + result["unsourced"] == result["items"]
    assert result["source_alignment"]["truth_verified"] is False


def test_checker_failure_is_closed_and_redacted(modules, monkeypatch):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    def fail(*args):
        raise RuntimeError("SENSITIVE_TEST_VALUE")
    monkeypatch.setattr(modules[0], "review_source_alignment", fail)
    result = modules[1].audit_source_titles("1. Förslag. Källa: JARVIS Prime", "JARVIS Prime")
    assert result["unsourced"] == 1
    assert result["source_alignment"]["statuses"] == ["check_failed"]
    assert "SENSITIVE_TEST_VALUE" not in str(result)


def run_reflect(audit, answer, context, required=True, baseline=0.9):
    tree = ast.parse((ROOT / "src/jarvis/core/supervisor.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "reflect")
    store = types.SimpleNamespace(enabled=False, upsert=lambda **kw: pytest.fail("memory write"))
    ns = {"JarvisState":dict, "_quality_score":lambda *args:baseline,
          "grounding_check":lambda body:{"checked":bool(body) and not body.startswith("[JARVIS-fel]") and body != "(tomt svar från modellen)",
              "items":1,"sourced":1,"unsourced":0},
          "audit_source_titles":audit,"UNGROUNDED_QUALITY_CAP":0.5,
          "_memory_store":store, "_should_persist_turn":lambda *args:False}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])), "isolated_reflect", "exec"),ns)
    state={"messages":[types.SimpleNamespace(content="Uppgift"),types.SimpleNamespace(content=answer)],
           "grounding":{"required":required},"memory_context":{"text":context},
           "frugality":{"fallback_errors":["synthetic fallback"]}}
    return asyncio.run(ns["reflect"](state))


@pytest.mark.parametrize("answer,context,expected", [
    ("1. Förslag. Källa: JARVIS Prime", "JARVIS Prime", 0.9),
    ("1. Försening. Källa: inget registrerat", "JARVIS Prime", 0.5),
    ("1. Förslag. Källa: JARVIS Prime", "", 0.5),
    ("1. Fel. Källa: Påhittad leverans", "JARVIS Prime", 0.5),
])
def test_reflect_consumes_real_audit_without_memory_writes(modules, monkeypatch, answer, context, expected):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    result = run_reflect(modules[1].audit_source_titles, answer, context)
    assert result["quality_score"] == expected
    assert result["frugality"]["fallback_errors"] == ["synthetic fallback"]


def test_reflect_never_raises_low_baseline(modules, monkeypatch):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    assert run_reflect(modules[1].audit_source_titles,
        "1. Saknas. Källa: inget registrerat", "JARVIS Prime",baseline=0.2)["quality_score"] == 0.2


@pytest.mark.parametrize("answer", ["", "(tomt svar från modellen)", "[JARVIS-fel] syntetiskt"])
def test_empty_and_errors_do_not_call_audit(modules, answer):
    def forbidden(*args):
        pytest.fail("unexpected audit")
    assert run_reflect(forbidden, answer, "", baseline=0.0)["quality_score"] == 0.0


def test_non_source_role_is_unchanged(modules, monkeypatch):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    assert run_reflect(modules[1].audit_source_titles,"Hej","",required=False)["quality_score"] == 0.9


def test_cancellation_propagates(modules, monkeypatch):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    def cancel(*args):
        raise asyncio.CancelledError()
    monkeypatch.setattr(modules[0], "review_source_alignment", cancel)
    with pytest.raises(asyncio.CancelledError):
        modules[1].audit_source_titles("1. Förslag. Källa: JARVIS Prime", "JARVIS Prime")


def test_checker_failure_caps_reflect(modules, monkeypatch):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    def fail(*args):
        raise ValueError("SENSITIVE_TEST_VALUE")
    monkeypatch.setattr(modules[0], "review_source_alignment", fail)
    result = run_reflect(modules[1].audit_source_titles,
        "1. Förslag. Källa: JARVIS Prime", "JARVIS Prime")
    assert result["quality_score"] == 0.5
    assert "SENSITIVE_TEST_VALUE" not in str(result)


def test_size_limit_blocks(modules, monkeypatch):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    result = modules[1].audit_source_titles("1. Förslag. Källa: JARVIS Prime", "x" * 64001)
    assert result["unsourced"] == 1
    assert result["source_alignment"]["statuses"] == ["input_limit_exceeded"]


def test_sensitive_input_is_not_copied_to_metadata(modules, monkeypatch):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    result = modules[1].audit_source_titles(
        "1. SENSITIVE_TEST_VALUE. Källa: inget registrerat", "SENSITIVE_CONTEXT_VALUE")
    assert "SENSITIVE_TEST_VALUE" not in str(result)
    assert "SENSITIVE_CONTEXT_VALUE" not in str(result)


def test_format_missing_is_not_reclassified_as_supported(modules, monkeypatch):
    monkeypatch.setenv("JARVIS_STRICT_SOURCE_ALIGNMENT", "1")
    result = modules[1].audit_source_titles("1. Ingen hänvisning", "JARVIS Prime")
    assert result["format_unsourced"] == 1
    assert result["sourced"] == 0
    assert result["unsourced"] == 1
