"""JARVIS Supervisor — LangGraph-pipeline med Frugality Agent och kostnadsdimmer.

Flöde per turn:
  classify_intent → route (välj agent-roll) → frugality_preflight
    → execute (anropa vald provider/modell) → reflect (mät kvalitet)
    → frugality_audit (eskalera vid under floor + AVISERA)
"""
from __future__ import annotations

import os
from uuid import uuid4
import re
import time
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from openai import AsyncOpenAI

from ..intelligence.source_references import audit_source_titles
from ..agents.frugality import FrugalityAgent
from ..approval.gate import ApprovalGate, classify_risk
from ..memory.context import build_context
from ..memory.store import MemoryStore
from ..notify.sinks import format_alerts, notify_all
from ..routing.providers import ProviderCatalog
from ..routing.tiers import Sensitivity, Tier
from .state import IntentClassification, JarvisState


BASE_SYSTEM = (
    "Du är JARVIS Ω∞ OS — Ricky Raippalinnas strategiska hjärna och operativa genomförare. "
    "Svara alltid på svenska, direkt och konkret, med slutsatsen först.\n"
    "Svara EXAKT på det som efterfrågas: ber uppgiften om numrerade punkter, en rad eller "
    "'max N ord' så följer du det och lägger inte till tomma rubriker.\n"
    "Vid strategiska beslut (rekommendation, prioritering, vägval) använder du ordningen: "
    "Slutsats, Möjligheter, Risker, Dolda risker, Hävstång, Rekommendation, Nästa steg.\n"
    "Skilj verifierat faktum, beräkning, antagande och förslag. Kvantifiera kr-effekt, "
    "tidshorisont och sannolikhet när underlag finns; annars skriv att underlag saknas. "
    "Hitta aldrig på siffror, källor eller genomförda åtgärder. Undvik fluff och generiska svar. "
    "Testa det starkaste motargumentet innan du rekommenderar."
)

ROLE_PROMPTS = {
    "researcher": "Du är forsknings- och marknadsanalytiker. Fokus: marknadsstorlek, aktörer, trender, källor.",
    "coder": "Du är systemarkitekt och seniorutvecklare. Ge konkret kod, filstruktur, kommandon.",
    "analyst": "Du är kapitalallokerare och operativ strateg. Räkna ROI, payback, brytpunkter.",
    "architect": "Du är företagsarkitekt. Rita systemgränser, ansvar, godkännandegrindar.",
    "casual": "Kort, direkt konversation. Behåll RICKY Ω∞ OS-formatet vid strategiska frågor.",
    "strategist": (
        "Du är operativ strateg och multiplikator för Ricky. Svara EXAKT på det som "
        "efterfrågas i uppgiften (t.ex. flaskhals, hävstång, prioritering, reaktion på "
        "förändring) — byt INTE ämne till generell marknadsanalys eller en ospecifik "
        "branschgenomgång om det inte uttryckligen efterfrågas. Håll dig strikt till "
        "vad frågan faktiskt ber om."
    ),
}


# ---------------------------------------------------------------------------
# Router-hjälpare
# ---------------------------------------------------------------------------

def _classify_category(text: str) -> tuple[str, float]:
    t = text.lower()
    if any(k in t for k in ("kod", "python", "api", "endpoint", "workflow", "script")):
        return "coding", 0.85
    if any(k in t for k in (
        "flaskhals", "hävstång", "prioritering", "initiativ", "ekosystem",
        "statuscheck", "veckobrief", "veckobriefing", "frugality", "reaktion",
        "bottleneck", "beslutslogg",
    )):
        return "strategy", 0.85
    if any(k in t for k in ("research", "marknad", "undersök", "trend", "aktörer")):
        return "research", 0.85
    if any(k in t for k in ("analys", "roi", "kostnad", "payback", "kalkyl", "kassaflöde")):
        return "analysis", 0.85
    if any(k in t for k in ("arkitektur", "system", "design", "flöde")):
        return "architecture", 0.8
    if any(k in t for k in ("hej", "tja", "yo", "hur mår")):
        return "casual", 0.9
    return "unknown", 0.5


def _intent_to_role(cat: str) -> str:
    return {
        "research": "researcher",
        "coding": "coder",
        "analysis": "analyst",
        "architecture": "architect",
        "casual": "casual",
        "strategy": "strategist",
        # Okänd intent-kategori ska INTE tolkas som en marknadsanalysfråga --
        # den generiska RICKY-strategrollen är ett mycket säkrare default-antagande.
        "unknown": "strategist",
    }.get(cat, "strategist")


def _intent_to_handoff_trigger(cat: str) -> str:
    return {
        "research": "market_research_interactive",
        "coding": "formula_generation",
        "analysis": "financial_model",
        "architecture": "long_document_draft",
        "casual": "casual",
        "strategy": "executive_summary",
    }.get(cat, "executive_summary")


def _sensitivity_from_text(text: str) -> Sensitivity:
    t = text.lower()
    if any(k in t for k in ("avtal", "kontrakt", "kunddata", "faktura", "betala")):
        return Sensitivity.CONFIDENTIAL
    if any(k in t for k in ("löner", "personnummer", "hemlig")):
        return Sensitivity.SECRET
    return Sensitivity.INTERNAL


def _tier_from_env(fallback: Tier = Tier.LOW) -> Tier:
    return Tier.from_str(os.environ.get("JARVIS_TIER", ""), default=fallback)


_STRATEGIC_MARKERS = {
    "Slutsats": ("slutsats",),
    "Möjligheter": ("möjlighet",),
    "Risker": ("risk",),
    "Rekommendation": ("rekommend",),
    "Nästa steg": ("nästa steg", "handling", "åtgärd"),
}
_STRATEGIC_TASK_HINTS = (
    "rekommend", "strateg", "briefing", "brief", "prioriter", "vägval", "ska jag",
    "analysera", "bedöm", "beslut", "möjligheter", "risker",
)
_QUANTIFIERS = (" kr", "kr/", "sek", "%", "sannolikhet", "timmar", "dagar", "veckor", "tkr", "mkr")


def _is_error_answer(text: str) -> bool:
    return str(text).lstrip().startswith("[JARVIS-fel]")


_EMPTY_MODEL_ANSWER = "(tomt svar från modellen)"


def _should_persist_turn(user_text: str, answer: str) -> bool:
    """Avgör om en tur får sparas som samtalsminne.

    Systemfel, tomma svar och platshållaren för tomt modellsvar är inte
    kunskap och får aldrig återläsas som kontext i senare körningar.
    """
    if not str(user_text or "").strip():
        return False
    body = str(answer or "").strip()
    if not body or body == _EMPTY_MODEL_ANSWER:
        return False
    if _is_error_answer(body):
        return False
    return True


def _requested_word_limit(task: str) -> Optional[int]:
    m = re.search(r"max\s*(\d{2,4})\s*ord", str(task), flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def _requested_item_count(task: str) -> int:
    """Antal explicit begärda delfrågor, t.ex. '(1) ... (2) ... (3)'."""
    nums = {int(n) for n in re.findall(r"\((\d)\)", str(task))}
    return len(nums)


def _answer_item_count(text: str) -> int:
    """Antal numrerade punkter/rubriker i svaret (1., 1), (1), ### 1, **1.**)."""
    nums = set()
    for m in re.finditer(r"(?m)^\W{0,6}(\d)[.)]", str(text)):
        nums.add(int(m.group(1)))
    for m in re.finditer(r"\((\d)\)", str(text)):
        nums.add(int(m.group(1)))
    return len(nums)


def _is_strategic_task(task: str, text: str) -> bool:
    t = str(task).lower()
    if _requested_item_count(task) >= 2 or _requested_word_limit(task):
        return False
    if any(h in t for h in ("en rad", "kort", "ja/nej", "bekräfta", "kopplingstest")):
        return False
    if any(h in t for h in _STRATEGIC_TASK_HINTS):
        return True
    return len(str(text).split()) > 250


GROUNDING_RULE = (
    "GRUNDNINGSREGEL: Händelser, förändringar, siffror och status får bara hämtas ur "
    "blocket MINNE OCH KONTEXT eller ur själva uppgiften. Saknas underlag för en delfråga: "
    "skriv 'Inget registrerat i minnet' och ange vad som skulle behöva loggas — "
    "hitta aldrig på en händelse, ett fel eller en åtgärd. Märk egna bedömningar som antagande."
)


SOURCE_FOOTER = (
    "KÄLLKRAV: Avsluta varje numrerad punkt med raden \"Källa: <post i MINNE OCH KONTEXT>\" "
    "(t.ex. \"Källa: Notion/Initiativ – JARVIS Prime\" eller \"Källa: wiki – jarvis-prime-systembygge\"). "
    "Finns ingen post som stöder punkten: skriv exakt \"Källa: inget registrerat\" och säg vad som "
    "borde loggas. Händelser, leveranser, möten, personer och siffror som inte står i källtexten "
    "får inte förekomma."
)

# Roller där svaret bygger på källtext och därför måste källmärkas. Kod och
# småprat källmärks inte.
_SOURCE_REQUIRED_ROLES = {"strategist", "analyst", "researcher", "architect"}

# Källmärkningen godtas både som egen rad och inline i slutet av punkten:
# driftkörning 41994995349 skrev "... kostnader. Källa: Beslutslogg – ..." på samma rad.
_SOURCE_LINE_RE = re.compile(r"(?i)\bkälla[^\S\r\n]*:[^\S\r\n*`_]*[*`_]*[^\S\r\n]*(?=[^\s*`_])")
_NONE_REGISTERED_RE = re.compile(r"(?i)källa\s*:\s*\**\s*inget registrerat")
_ITEM_START_RE = re.compile(r"(?m)^[^\w\r\n]{0,6}(\d+)[.)]")


def grounding_check(answer: str) -> Dict[str, Any]:
    """Deterministisk källkontroll: har varje numrerad punkt en 'Källa:'-rad?

    Mäter bara att påståenden bär en källhänvisning till kontexten – inte att
    hänvisningen är sann. Saknad källa är det billigaste tecknet på påhitt:
    en modell som hittar på en leverans eller ett möte kan inte peka på en post.
    """
    body = str(answer or "").strip()
    if not body or body == _EMPTY_MODEL_ANSWER or _is_error_answer(body):
        return {"checked": False, "items": 0, "sourced": 0, "unsourced": 0, "none_registered": 0}
    starts = [m.start() for m in _ITEM_START_RE.finditer(body)]
    segments = (
        [body[a:b] for a, b in zip(starts, starts[1:] + [len(body)])] if starts else [body]
    )
    sourced = sum(1 for seg in segments if _SOURCE_LINE_RE.search(seg))
    return {
        "checked": True,
        "items": len(segments),
        "sourced": sourced,
        "unsourced": len(segments) - sourced,
        "none_registered": len(_NONE_REGISTERED_RE.findall(body)),
    }


# Tak för kvalitetspoängen när minst en punkt saknar källa. Ligger under alla
# tier-golv (lägst FREE 0.60) så att den befintliga under_floor-larmkedjan reagerar.
UNGROUNDED_QUALITY_CAP = 0.5


def _memory_block(mem: Dict[str, Any]) -> str:
    """Bygger MINNE-blocket för systemprompten.

    Tomt minne skrivs ut explicit med orsak (t.ex. nyckelroll=anon) så modellen
    vet att det saknas underlag i stället för att fylla luckan med gissningar.
    """
    text = (mem or {}).get("text", "") or ""
    summary = (mem or {}).get("summary", "") or ""
    if text.strip():
        head = f"--- MINNE OCH KONTEXT ({summary}) ---" if summary else "--- MINNE OCH KONTEXT ---"
        return f"{head}\n{text}\n--- SLUT MINNE ---"
    reason = f" Orsak: {summary}." if summary else ""
    return (
        "--- MINNE OCH KONTEXT ---\n"
        f"TOMT: inga minnesposter, Notion-poster eller loggade körningar kunde läsas.{reason} "
        "Du vet därför INGET om vad som hänt nyligen.\n"
        "--- SLUT MINNE ---"
    )


def _quality_score(text: str, task: str = "") -> float:
    """Kvalitetsscore 0–1 som mäter det uppgiften faktiskt bad om.

    - Fel- eller tomt svar → 0.0 (ett felmeddelande får aldrig poäng för att det
      råkar innehålla 'kr').
    - Strategiska uppgifter mäts mot RICKY Ω∞ OS-strukturen plus kvantifiering.
    - Direkta uppgifter (numrerade delfrågor, ordgräns, 'svara med en rad') mäts på
      att alla delfrågor besvaras, att ordgränsen hålls och att svaret är konkret.
    Tidigare version gav 0.15 åt korrekta korta svar och åt 503-fel, vilket
    utlöste falska KVALITETSAVVIKELSE-larm.
    """
    body = str(text or "").strip()
    if not body or body == _EMPTY_MODEL_ANSWER or _is_error_answer(body):
        return 0.0
    low = body.lower()
    quantified = any(q in low for q in _QUANTIFIERS)

    if _is_strategic_task(task, body):
        hits = sum(1 for keys in _STRATEGIC_MARKERS.values() if any(k in low for k in keys))
        base = hits / len(_STRATEGIC_MARKERS)
        if quantified:
            base = min(1.0, base + 0.15)
        return round(base, 2)

    # Direkt uppgift
    score = 0.8
    wanted = _requested_item_count(task)
    if wanted >= 2:
        got = _answer_item_count(body)
        if got >= wanted:
            score += 0.1
        else:
            score -= 0.25 * (wanted - got) / wanted
    limit = _requested_word_limit(task)
    if limit:
        words = len(body.split())
        if words <= limit:
            score += 0.05
        elif words > limit * 1.5:
            score -= 0.2
    if quantified:
        score += 0.05
    return round(max(0.0, min(1.0, score)), 2)


# ---------------------------------------------------------------------------
# LangGraph-noder
# ---------------------------------------------------------------------------

_catalog = ProviderCatalog()
_frugality = FrugalityAgent(_catalog)
_memory_store = MemoryStore()
_approval = ApprovalGate()


async def classify_intent(state: JarvisState) -> JarvisState:
    if not state["messages"]:
        return state
    text = str(state["messages"][-1].content)
    cat, conf = _classify_category(text)
    state["intent"] = IntentClassification(category=cat, confidence=conf)
    return state


async def route(state: JarvisState) -> JarvisState:
    cat = state["intent"].category if state.get("intent") else "unknown"
    state["active_agents"] = [_intent_to_role(cat)]
    state["routing_confidence"] = state["intent"].confidence if state.get("intent") else 0.5
    return state


async def approval_gate(state: JarvisState) -> JarvisState:
    """Godmode-grinden: R0/R1 loggas och går vidare direkt. R2/R3 skapar en
    riktig rad i approval_decision/approval_request och HALTAR turen -- ingen
    LLM anropas, ingen extern åtgärd sker, förrän Ricky godkänt.
    Deterministisk regel, ingen LLM avgör sig själv förbi grinden.
    """
    text = str(state["messages"][-1].content) if state["messages"] else ""
    cat = state["intent"].category if state.get("intent") else "unknown"
    risk = classify_risk(text, cat)
    session_id = state.get("session_id", "")

    if risk.requires_approval:
        request_id = _approval.open_gate(text, risk, session_id)
        state["approval"] = {
            "halted": True,
            "risk_class": risk.risk_class,
            "reason": risk.reason,
            "request_id": request_id,
        }
    else:
        _approval.log_auto(text, risk, session_id)
        state["approval"] = {
            "halted": False,
            "risk_class": risk.risk_class,
            "reason": risk.reason,
            "request_id": None,
        }
    return state


def _approval_route(state: JarvisState) -> str:
    return "halt" if state.get("approval", {}).get("halted") else "continue"


async def await_approval(state: JarvisState) -> JarvisState:
    """Terminal nod för R2/R3: skriver ett tydligt vänteläge-svar, aviserar
    Ricky direkt via samma Slack/Notion-sinkar som Frugality använder, och
    avslutar turen UTAN att någon LLM anropats eller någon extern åtgärd
    exekverats.
    """
    approval = state.get("approval", {})
    prev_task = str(state["messages"][-1].content) if state["messages"] else ""
    answer = (
        f"\u23f8\ufe0f GODMODE-GRIND ({approval.get('risk_class')}): den här uppgiften "
        f"kräver ditt godkännande innan JARVIS kör den.\n\n"
        f"Skäl: {approval.get('reason')}\n"
        f"Approval-ID: {approval.get('request_id') or '(kunde inte skapas i Supabase -- kolla SUPABASE_SERVICE_ROLE_KEY)'}\n\n"
        f"INGEN extern åtgärd, betalning eller kommunikation har skett. "
        f"Säg till Ricky (eller be Perplexity Computer) att godkänna eller avslå raden "
        f"i approval_decision/approval_request innan detta körs autonomt igen."
    )
    state["messages"].append(AIMessage(content=answer))
    state["quality_score"] = 1.0  # detta ÄR korrekt beteende, inte ett fel
    state["frugality"] = {
        "tier": "GATE",
        "provider": "approval_gate",
        "model": "none",
        "est_cost_sek": 0.0,
        "rationale": f"Approval gate: {approval.get('risk_class')} -- {approval.get('reason')}",
        "alerts": [f"GODMODE-GRIND öppnad: {approval.get('reason')}"],
        "handoff": None,
        "est_input_tokens": 0,
        "est_output_tokens": 0,
        "actual_cost_sek": 0.0,
        "actual_input_tokens": 0,
        "actual_output_tokens": 0,
        "latency_ms": 0,
    }
    if os.environ.get("JARVIS_NOTIFY", "1") != "0":
        notify_all(
            "\U0001f512 JARVIS väntar på ditt godkännande",
            f"Risk: {approval.get('risk_class')}\nSkäl: {approval.get('reason')}\n"
            f"Uppgift: {prev_task[:300]}\nApproval-ID: {approval.get('request_id')}",
        )
    return state


async def load_memory(state: JarvisState) -> JarvisState:
    """Hämta relevant historik + Notion + wiki innan LLM-anrop."""
    text = str(state["messages"][-1].content)
    sensitivity = _sensitivity_from_text(text)
    allowed = {
        Sensitivity.PUBLIC: ["public"],
        Sensitivity.INTERNAL: ["public", "internal"],
        Sensitivity.CONFIDENTIAL: ["public", "internal", "confidential"],
        Sensitivity.SECRET: ["public", "internal", "confidential", "secret"],
    }[sensitivity]
    bundle = build_context(query=text, allowed_sensitivity=allowed, max_chars=4000)
    state["memory_context"] = {
        "text": bundle.text,
        "sources": bundle.sources_used,
        "hits_vector": bundle.hits_vector,
        "hits_wiki": bundle.hits_wiki,
        "hits_recent": bundle.hits_recent,
        "hits_log": bundle.hits_log,
        "notion_used": bundle.notion_used,
        "diagnostics": bundle.diagnostics,
        "summary": bundle.summary(),
    }
    return state


async def frugality_preflight(state: JarvisState) -> JarvisState:
    text = str(state["messages"][-1].content)
    cat = state["intent"].category if state.get("intent") else "unknown"
    tier = _tier_from_env()
    sensitivity = _sensitivity_from_text(text)
    month_pct = float(os.environ.get("JARVIS_MONTH_SPEND_PCT", "0"))

    est_in = min(4000, 200 + len(text) // 3)
    est_out = 900

    # Handoff till manuella UI-kanaler (Copilot i Word osv.) är meningslöst när
    # ingen människa sitter vid körningen; jarvis_cloud sätter JARVIS_ALLOW_HANDOFF=0.
    allow_handoff = os.environ.get("JARVIS_ALLOW_HANDOFF", "1") != "0"
    decision = _frugality.pre_flight(
        allow_handoff=allow_handoff,
        intent=_intent_to_handoff_trigger(cat),
        tier=tier,
        est_input_tokens=est_in,
        est_output_tokens=est_out,
        sensitivity=sensitivity,
        month_spend_pct=month_pct,
    )
    state["frugality"] = {
        "tier": decision.route.tier.value,
        "provider": decision.route.provider.key,
        "model": decision.route.model_id,
        "est_cost_sek": decision.route.est_cost_sek,
        "rationale": decision.route.rationale,
        "alerts": decision.alerts,
        "handoff": {
            "channel": decision.handoff.channel_key,
            "display": decision.handoff.display_name,
            "savings_sek": decision.handoff.savings_sek,
            "ux_note": decision.handoff.ux_note,
        } if decision.handoff else None,
        "est_input_tokens": est_in,
        "est_output_tokens": est_out,
    }
    return state


async def execute(state: JarvisState) -> JarvisState:
    fr = state["frugality"]

    role = (state.get("active_agents") or ["researcher"])[0]
    role_prompt = ROLE_PROMPTS.get(role, ROLE_PROMPTS["researcher"])
    user_content = str(state["messages"][-1].content)

    mem = state.get("memory_context", {})
    system_prompt = (
        f"{BASE_SYSTEM}\n\nROLL: {role_prompt}\n\n{GROUNDING_RULE}\n\n{_memory_block(mem)}"
    )
    # Källkravet läggs intill själva uppgiften: små modeller följer formatkrav
    # som står bredvid frågan bättre än regler långt upp i systemprompten.
    source_required = role in _SOURCE_REQUIRED_ROLES
    if source_required:
        user_content = f"{user_content}\n\n{SOURCE_FOOTER}"
    state["grounding"] = {"required": source_required}

    # Bygg en anropslista: frugality-agentens primärval först, sedan resten av
    # SAMMA tier-kedja som runtime-fallback. Löser buggen där ett enskilt
    # modell-namn som blivit ogiltigt hos leverantören (t.ex. en utfasad
    # Claude-modellsträng på Comet) fick HELA turen att bara skriva ett
    # felmeddelande till Notion istället för att verkligen prova nästa
    # kandidat i kedjan.
    tier_chain = _catalog.tiers.get(fr["tier"], {}).get("chain", [])
    candidates = [(fr["provider"], fr["model"])]
    for step in tier_chain:
        pair = (step["provider"], step["model"])
        if pair not in candidates:
            candidates.append(pair)

    answer: Optional[str] = None
    actual_cost = 0.0          # summerad över ALLA debiterbara försök, även tomma svar
    in_tok, out_tok = fr["est_input_tokens"], fr["est_output_tokens"]
    used_provider_key, used_model = fr["provider"], fr["model"]
    errors: List[str] = []
    empty_answers = 0

    start = time.perf_counter()
    for provider_key, model_id in candidates:
        provider = _catalog.get(provider_key)
        api_key = os.environ.get(provider.api_key_env, "")
        if not api_key:
            errors.append(f"{provider.key}/{model_id}: {provider.api_key_env} saknas")
            continue
        try:
            client = AsyncOpenAI(api_key=api_key, base_url=provider.base_url)
            resp = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.4,
            )
            usage = getattr(resp, "usage", None)
            in_tok = getattr(usage, "prompt_tokens", fr["est_input_tokens"]) if usage else fr["est_input_tokens"]
            out_tok = getattr(usage, "completion_tokens", fr["est_output_tokens"]) if usage else fr["est_output_tokens"]
            # Ett anrop som kom fram debiteras oavsett om innehållet var tomt.
            actual_cost += provider.estimate_cost_sek(in_tok, out_tok)
            choices = getattr(resp, "choices", None) or []
            content = (choices[0].message.content if choices else None) or ""
            if not content.strip():
                # Tomt svar är inte ett svar: prova nästa kandidat i kedjan
                # i stället för att avsluta turen med en platshållare.
                empty_answers += 1
                errors.append(f"{provider.key}/{model_id}: tomt svar från modellen")
                continue
            answer = content
            used_provider_key, used_model = provider_key, model_id
            break
        except Exception as exc:
            errors.append(f"{provider.key}/{model_id}: {type(exc).__name__}: {exc}")
            continue

    hard_failures = [
        e for e in errors
        if not (e.endswith("tomt svar från modellen") or e.endswith(" saknas"))
    ]
    if answer is None and empty_answers and not hard_failures:
        # Alla nåbara kandidater svarade tomt: behåll den kända platshållaren
        # så att reflect/minne fortsätter att känna igen och utesluta den.
        answer = "(tomt svar från modellen)"
    elif answer is None:
        answer = (
            f"[JARVIS-fel] Alla {len(candidates)} kandidater i tier={fr['tier']}-kedjan misslyckades:\n"
            + "\n".join(f"- {e}" for e in errors)
            + f"\n\nFrugality valde ursprungligen: {fr['rationale']}"
        )

    latency_ms = int((time.perf_counter() - start) * 1000)

    state["messages"].append(AIMessage(content=answer))
    state["frugality"]["provider"] = used_provider_key
    state["frugality"]["model"] = used_model
    if errors:
        state["frugality"]["fallback_errors"] = errors
    state["frugality"]["actual_cost_sek"] = actual_cost
    state["frugality"]["actual_input_tokens"] = in_tok
    state["frugality"]["actual_output_tokens"] = out_tok
    state["frugality"]["latency_ms"] = latency_ms
    return state


async def reflect(state: JarvisState) -> JarvisState:
    last = state["messages"][-1].content if state["messages"] else ""
    task_text = str(state["messages"][-2].content) if len(state["messages"]) >= 2 else ""
    state["quality_score"] = _quality_score(str(last), task_text)
    grounding = dict(state.get("grounding") or {})
    if grounding.get("required"):
        grounding.update(grounding_check(str(last)))
        if grounding.get("checked"):
            context_text = str((state.get("memory_context") or {}).get("text") or "")
            grounding.update(audit_source_titles(str(last), context_text))
        if grounding.get("checked") and (
            grounding.get("unsourced", 0) > 0 or
            grounding.get("unmatched_titles", 0) > 0
        ):
            grounding["quality_capped"] = True
            state["quality_score"] = min(state["quality_score"], UNGROUNDED_QUALITY_CAP)
    state["grounding"] = grounding
    # Spara turen som ny minneschunk (fire-and-forget)
    try:
        user_text = str(state["messages"][-2].content) if len(state["messages"]) >= 2 else ""
        if _memory_store.enabled and _should_persist_turn(user_text, str(last)):
            sens = _sensitivity_from_text(user_text).value
            _memory_store.upsert(
                content=f"Q: {user_text}\nA: {str(last)[:2000]}",
                source="conversation",
                source_ref=state.get("session_id", ""),
                kind="chunk",
                title=f"turn:{state.get('current_user_id','?')}",
                metadata={"tier": state.get('frugality',{}).get('tier'),
                          "quality": state["quality_score"]},
                sensitivity=sens,
            )
    except Exception:
        pass
    return state


async def frugality_audit(state: JarvisState) -> JarvisState:
    fr = state["frugality"]
    tier = Tier.from_str(fr["tier"])
    floor = float(_catalog.tiers[tier.value]["quality_floor"])
    quality = state.get("quality_score", 0.0)

    from dataclasses import dataclass  # local import to avoid re-imports
    # Rekonstruera minimal FrugalityDecision för audit-anrop
    from ..agents.frugality import FrugalityDecision
    from ..routing.tiers import RouteDecision
    route_min = RouteDecision(
        tier=tier,
        provider=_catalog.get(fr["provider"]),
        model_id=fr["model"],
        quality_index=0.0,
        est_cost_sek=fr["est_cost_sek"],
        rationale=fr["rationale"],
        frugality_notes=[],
    )
    decision = FrugalityDecision(route=route_min, handoff=None, alerts=list(fr.get("alerts", [])))
    report = _frugality.audit(
        decision=decision,
        actual_quality=quality,
        actual_cost_sek=fr.get("actual_cost_sek", 0.0),
        latency_ms=fr.get("latency_ms", 0),
    )
    state["frugality"]["audit"] = report

    # Avisera vid avvikelser
    alerts = report.get("alerts", [])
    if report.get("under_floor") or any(a.startswith(("BUDGET-VARNING", "BUDGET-KRIS", "HANDOFF-FÖRSLAG", "KVALITETSAVVIKELSE")) for a in alerts):
        title = f"🟡 JARVIS Frugality-avvikelse (tier={tier.value})"
        body = (
            f"Provider: {fr['provider']} / {fr['model']}\n"
            f"Kvalitet: {quality} (floor {floor})\n"
            f"Kostnad: {report['actual_cost_sek']} kr (est {report['est_cost_sek']})\n"
            f"Latens: {report['latency_ms']} ms\n\n"
            f"Alerts:\n{format_alerts(alerts) or '—'}"
        )
        if os.environ.get("JARVIS_NOTIFY", "1") != "0":
            state["frugality"]["notify_result"] = notify_all(title, body)
    return state


def create_graph():
    g = StateGraph(JarvisState)
    for name, fn in [
        ("classify_intent", classify_intent),
        ("route", route),
        ("approval_gate", approval_gate),
        ("await_approval", await_approval),
        ("load_memory", load_memory),
        ("frugality_preflight", frugality_preflight),
        ("execute", execute),
        ("reflect", reflect),
        ("frugality_audit", frugality_audit),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "classify_intent")
    g.add_edge("classify_intent", "route")
    g.add_edge("route", "approval_gate")
    g.add_conditional_edges(
        "approval_gate", _approval_route, {"halt": "await_approval", "continue": "load_memory"}
    )
    g.add_edge("await_approval", END)
    g.add_edge("load_memory", "frugality_preflight")
    g.add_edge("frugality_preflight", "execute")
    g.add_edge("execute", "reflect")
    g.add_edge("reflect", "frugality_audit")
    g.add_edge("frugality_audit", END)
    return g.compile()


class Supervisor:
    def __init__(self):
        self.graph = create_graph()

    async def chat(self, messages: List[BaseMessage], user_id: str = "test", **kw) -> Dict[str, Any]:
        norm: List[BaseMessage] = []
        for m in messages:
            if isinstance(m, BaseMessage):
                norm.append(m)
            elif isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                norm.append(AIMessage(content=content) if role == "assistant" else HumanMessage(content=content))
        state: JarvisState = {
            "messages": norm,
            "current_user_id": user_id,
            "session_id": kw.get("session_id") or uuid4().hex,
            "intent": None,
            "active_agents": [],
            "routing_confidence": 0.0,
            "quality_score": 0.0,
            "frugality": {},
            "memory_context": {},
            "approval": None,
        }
        return await self.graph.ainvoke(state)


supervisor = Supervisor()
