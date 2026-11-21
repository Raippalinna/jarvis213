"""Build scoped reference data, never privileged system instructions.

Use identity-filtered text memory. Legacy shared Notion/wiki sources are opt-in
and treated as confidential until proper per-item labels exist.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from .notion_room import NotionControlRoom
from .store import MemoryStore
from .wiki import WikiReader
from .access import MemoryScope
from ..safety.secrets import contains_secret


@dataclass
class ContextBundle:
    text: str
    sources_used: List[str]
    hits_vector: int
    hits_wiki: int
    notion_used: bool
    sensitivity: str = "public"


def build_context(
    query: str,
    allowed_sensitivity: Optional[List[str]] = None,
    max_chars: int = 4000,
    vector_top_k: int = 5,
    wiki_top_k: int = 2,
    scope: Optional[MemoryScope] = None,
) -> ContextBundle:
    """Bygg minneskontext för aktuell task-fråga."""
    sources: List[str] = []
    parts: List[str] = []
    hits_vec = 0
    hits_wiki = 0
    notion_used = False
    sensitivity = "public"
    if scope is None or contains_secret(query):
        return ContextBundle("", [], 0, 0, False)
    allowed_sensitivity = [
        level for level in scope.allowed_levels
        if allowed_sensitivity is None or level in allowed_sensitivity
    ]
    if not allowed_sensitivity:
        return ContextBundle("", [], 0, 0, False)

    # 1. Vektorminne
    store = MemoryStore()
    if store.enabled:
        hits = store.search(
            query_text=query,
            match_count=vector_top_k,
            allowed_sensitivity=allowed_sensitivity,
            scope=scope,
        )
        hits_vec = len(hits)
        if hits:
            sources.append("scoped_text_memory")
            levels = ["public", "internal", "confidential"]
            sensitivity = max((h.sensitivity for h in hits), key=levels.index)
            block = "\n".join(h.to_context_line() for h in hits)
            parts.append(f"### Relevant historik (semantiskt minne)\n{block}")

    # 2. Notion Control Room
    room = NotionControlRoom()
    db_ids = {
        "Beslutslogg": os.environ.get("NOTION_DB_BESLUTSLOGG", "").strip(),
        "Initiativ": os.environ.get("NOTION_DB_INITIATIV", "").strip(),
        "Inkomst-radar": os.environ.get("NOTION_DB_RADAR", "").strip(),
    }
    # Legacy shared sources have no per-item labels. Require explicit owner
    # approval and confidential clearance instead of pretending they are public.
    shared_allowed = scope.shared_context and "confidential" in allowed_sensitivity
    if shared_allowed and room.enabled and any(db_ids.values()):
        notion_brief = room.brief(db_ids, per_db=5)
        if notion_brief and not contains_secret(notion_brief):
            sensitivity = "confidential"
            notion_used = True
            sources.append("notion")
            parts.append(f"### Aktivt kontrollrum (Notion)\n{notion_brief}")

    # 3. Wiki (arkitektoniska beslut)
    wiki = WikiReader()
    if shared_allowed and wiki.enabled:
        wiki_brief = wiki.brief(query, max_results=wiki_top_k)
        if wiki_brief and not contains_secret(wiki_brief):
            sensitivity = "confidential"
            hits_wiki = wiki_brief.count("### ")
            sources.append("wiki")
            parts.append(f"### Arkitektoniska beslut (wiki)\n{wiki_brief}")

    joined = "\n\n".join(parts).strip()
    if len(joined) > max_chars:
        joined = joined[: max_chars - 20].rstrip() + "\n[trimmed]"
    return ContextBundle(
        text=joined,
        sources_used=sources,
        hits_vector=hits_vec,
        hits_wiki=hits_wiki,
        notion_used=notion_used,
        sensitivity=sensitivity,
    )
