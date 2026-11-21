"""Regressionstester: runtime-fallback får aldrig kringgå routerpolicy eller läcka API-fel."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

from jarvis.core import supervisor as sv
from jarvis.routing.tiers import Sensitivity


def allowed(provider_key, model_id, tier, sensitivity, tokens=300):
    return sv._runtime_candidate_allowed(
        sv._catalog.get(provider_key), model_id,
        sv._catalog.tiers[tier], sensitivity, tokens, tokens,
    )


def test_allowed_internal_low_candidate():
    assert allowed("comet_low", "gpt-4o-mini", "LOW", Sensitivity.INTERNAL)


def test_unlisted_model_or_tier_rejected():
    assert not allowed("comet_low", "not-in-catalog", "LOW", Sensitivity.INTERNAL)
    assert not sv._runtime_candidate_allowed(
        sv._catalog.get("comet_low"), "gpt-4o-mini", {},
        Sensitivity.INTERNAL, 300, 300,
    )


def test_sensitive_data_never_goes_to_free_or_low_tier():
    assert not allowed("groq", "llama-3.3-70b-versatile", "FREE", Sensitivity.CONFIDENTIAL)
    assert not allowed("comet_low", "gpt-4o-mini", "LOW", Sensitivity.SECRET)


def test_no_sensitive_content_to_training_provider_even_if_tier_allows_it():
    provider = replace(sv._catalog.get("comet_med"), trains_on_data=True)
    assert not sv._runtime_candidate_allowed(
        provider, "gpt-4o", sv._catalog.tiers["MED"],
        Sensitivity.CONFIDENTIAL, 100, 100,
    )


def test_quality_floor_and_cost_cap_apply_to_fallback():
    assert not allowed("comet_med", "gpt-4o", "HIGH", Sensitivity.SECRET)
    expensive = replace(sv._catalog.get("comet_low"), cost_per_1k_input_sek=99999)
    assert not sv._runtime_candidate_allowed(
        expensive, "gpt-4o-mini", sv._catalog.tiers["LOW"],
        Sensitivity.INTERNAL, 500, 500,
    )


def test_provider_exception_details_never_reach_user_or_audit(monkeypatch):
    secret = "TOP_SECRET_PROVIDER_RESPONSE_CONTENT"
    monkeypatch.setenv("COMET_API_KEY", "synthetic-test-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    class FakeCompletions:
        async def create(self, **kwargs):
            raise RuntimeError(secret)

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(sv, "AsyncOpenAI", FakeClient)
    state = {
        "messages": [HumanMessage(content="Ge ett kort testsvar.")],
        "active_agents": ["casual"],
        "memory_context": {},
        "frugality": {
            "tier": "LOW", "provider": "comet_low", "model": "gpt-4o-mini",
            "est_input_tokens": 200, "est_output_tokens": 100,
            "rationale": "synthetic test", "alerts": [],
            "est_cost_sek": 0.01,
        },
    }
    result = asyncio.run(sv.execute(state))
    assert secret not in result["messages"][-1].content
    assert secret not in str(result["frugality"])
    assert "RuntimeError (details redacted)" in result["messages"][-1].content
