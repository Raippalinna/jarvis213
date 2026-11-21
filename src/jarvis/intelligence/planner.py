"""Explicit domain routing, not an LLM router or an executing agent swarm."""
from __future__ import annotations

DOMAINS = {
    "mathematics": ("mathematics_specialist", "Kontrollera antaganden och beräkningar."),
    "physics": ("physics_specialist", "Kontrollera enheter, material och fysikaliska antaganden."),
    "psychology": ("psychology_specialist", "Skilj observerat beteende från psykologisk tolkning."),
    "history": ("history_specialist", "Kontrollera datering, primärkällor och historisk kontext."),
    "philosophy": ("philosophy_specialist", "Pröva premisser, målkonflikter och starkaste motargument."),
    "software": ("software_specialist", "Granska gränssnitt, licens och säker testbarhet."),
}
ALIASES = {
    "matematik": "mathematics", "fysik": "physics", "psykologi": "psychology",
    "historia": "history", "filosofi": "philosophy", "mjukvara": "software",
}


def plan_research(
    task: str,
    domains: list[str] | tuple[str, ...] = (),
    *,
    complexity: str = "simple",
    max_sources: int = 3,
    max_calls: int = 7,
) -> dict:
    """Plan only explicitly requested specialties, at most one for simple tasks."""
    if not isinstance(task, str) or not task.strip():
        return {"state": "blocked", "reasons": ["task_required"], "roles": []}
    if not isinstance(complexity, str) or complexity not in {"simple", "multi_domain"}:
        return {"state": "blocked", "reasons": ["invalid_complexity"], "roles": []}
    if (type(max_sources) is not int or not 1 <= max_sources <= 3
            or type(max_calls) is not int or not 1 <= max_calls <= 7):
        return {"state": "blocked", "reasons": ["invalid_budget"], "roles": []}
    if not isinstance(domains, (list, tuple)) or any(not isinstance(d, str) for d in domains):
        return {"state": "blocked", "reasons": ["invalid_domains"], "roles": []}
    requested = list(dict.fromkeys(ALIASES.get(d.lower(), d.lower()) for d in domains))
    if any(d not in DOMAINS for d in requested):
        return {"state": "blocked", "reasons": ["unknown_domain"], "roles": []}
    selected = requested[:1 if complexity == "simple" else 3]
    roles = [
        {"role": DOMAINS[d][0], "domain": d, "state": "PLANERAT",
         "review_question": DOMAINS[d][1]}
        for d in selected
    ] or [{
        "role": "evidence_researcher", "domain": None, "state": "PLANERAT",
        "review_question": "Avgränsa påståendet och sök lästa, oberoende källor.",
    }]
    return {
        "state": "prepared", "roles": roles, "deferred_domains": requested[len(selected):],
        "budget": {"max_sources": max_sources, "max_calls": max_calls,
                   "cost_estimate": None},
        "agents_executed": 0, "models_called": 0,
    }
