"""Grundning av statuscheckar: tomt minne ska sägas rakt ut, inte fyllas med gissningar.

Bakgrund (verifierat 2026-09-25, körning 36187180521): svaret påstod att en
'säkerhetsläcka identifierats och åtgärdats idag' — ingenting sådant fanns i
något minneslager. Orsak: minneskontexten var tom och prompten sa inte att
den var tom. Dessa tester låser det nya beteendet.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.agents.frugality import FrugalityAgent  # noqa: E402
from jarvis.routing.tiers import Tier  # noqa: E402
from jarvis.core.supervisor import GROUNDING_RULE, _memory_block  # noqa: E402
from jarvis.memory.context import ContextBundle, build_context  # noqa: E402
from jarvis.memory.notion_room import format_log_line  # noqa: E402
from jarvis.memory.store import MemoryStore  # noqa: E402


def _jwt(role: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJIUzI1NiJ9.{payload}.sig"


# --- Nyckelroll -------------------------------------------------------------

def test_key_role_decodes_claim_without_leaking_value():
    assert MemoryStore(supabase_url="https://x.supabase.co", supabase_key=_jwt("anon")).key_role() == "anon"
    assert MemoryStore(supabase_url="https://x.supabase.co", supabase_key=_jwt("service_role")).key_role() == "service_role"


def test_key_role_handles_new_key_formats_and_garbage():
    mk = lambda k: MemoryStore(supabase_url="https://x.supabase.co", supabase_key=k).key_role()
    assert mk("sb_publishable_abc") == "publishable"
    assert mk("sb_secret_abc") == "secret_key"
    assert mk("not-a-jwt") == "unknown"
    assert mk("") == "missing"


# --- Tomt minne sägs rakt ut ------------------------------------------------

def test_empty_memory_block_states_emptiness_and_reason():
    block = _memory_block({"text": "", "summary": "pgvector=0 senaste=0 notion=nej logg=0 wiki=0 (nyckelroll=anon, minne=permission denied)"})
    assert "TOMT" in block
    assert "nyckelroll=anon" in block
    assert "vet därför INGET" in block


def test_filled_memory_block_carries_text_and_summary():
    block = _memory_block({"text": "• 2026-09-25 · PR #4 mergad", "summary": "logg=1"})
    assert "PR #4 mergad" in block
    assert "(logg=1)" in block
    assert "TOMT" not in block


def test_grounding_rule_forbids_invented_events():
    assert "hitta aldrig på" in GROUNDING_RULE
    assert "Inget registrerat i minnet" in GROUNDING_RULE


# --- build_context utan nycklar: inga nätanrop, tydlig diagnostik -----------

def test_build_context_without_credentials_reports_disabled(monkeypatch):
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "NOTION_TOKEN",
              "NOTION_DB_BESLUTSLOGG", "NOTION_DB_INITIATIV", "NOTION_DB_RADAR",
              "NOTION_LOG_PAGE_ID", "NOTION_PAGE_ID"):
        monkeypatch.delenv(k, raising=False)
    b = build_context("Vad ändrades idag?")
    assert b.diagnostics.get("store_probe") == "disabled"
    assert b.hits_recent == 0 and b.hits_log == 0
    assert "pgvector=0" in b.summary()


def test_bundle_summary_mentions_blocked_key():
    b = ContextBundle(text="", sources_used=[], hits_vector=0, hits_wiki=0, notion_used=False,
                      diagnostics={"key_role": "anon", "store_probe": "permission denied"})
    s = b.summary()
    assert "nyckelroll=anon" in s and "minne=permission denied" in s


def test_bundle_summary_is_quiet_when_healthy():
    b = ContextBundle(text="x", sources_used=["recent"], hits_vector=2, hits_wiki=1, notion_used=True,
                      hits_recent=3, hits_log=2, diagnostics={"key_role": "service_role", "store_probe": "ok"})
    s = b.summary()
    assert s.startswith("pgvector=2 senaste=3 notion=ja logg=2 wiki=1")
    assert "minne=" not in s


# --- Notion-logg komprimeras till en rad utan header ------------------------

def test_format_log_line_strips_header_and_collapses_whitespace():
    body = "Task: x\nTier: LOW  Provider: comet_low/gpt-4o-mini\nKvalitet: 0.95\n\n---\n\n1. Flaskhals: A\n2.   Handling: B\n"
    line = format_log_line("2026-09-25 20:41 UTC", "JARVIS · 2026-09-25 20:41 UTC · Verifiering", body)
    assert line.startswith("• 2026-09-25 20:41 UTC · JARVIS")
    assert "Kvalitet" not in line
    assert "1. Flaskhals: A 2. Handling: B" in line


# --- Handoff kan inte spara mer än anropet kostar --------------------------

def test_handoff_not_suggested_when_route_is_cheaper_than_savings():
    agent = FrugalityAgent()
    d = agent.pre_flight(intent="executive_summary", tier=Tier.LOW, est_input_tokens=300, est_output_tokens=200)
    assert d.route.est_cost_sek < 5.0, "förutsättning: LOW-anropet kostar under tröskeln"
    assert d.handoff is None
    assert not any(a.startswith("HANDOFF") for a in d.alerts)


def test_handoff_can_be_disabled_for_unattended_runs():
    agent = FrugalityAgent()
    d = agent.pre_flight(intent="executive_summary", tier=Tier.HIGH, est_input_tokens=4000,
                         est_output_tokens=4000, allow_handoff=False)
    assert d.handoff is None
