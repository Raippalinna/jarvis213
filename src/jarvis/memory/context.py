"""build_context — samlar minnesfragment från alla lager till en systemprompt.

Kombinerar:
1. pgvector-chunks (semantiskt passivt minne)
2. Notion Control Room-brief (strukturerat aktivt minne)
3. Wiki-utdrag (arkitektoniskt låst minne)

Returnerar ren text som injiceras EFTER BASE_SYSTEM men FÖRE role-prompt.
Klipper till max_chars för att inte spränga token-cap.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from .notion_room import NotionControlRoom
from .store import MemoryStore
from .wiki import WikiReader


@dataclass
class ContextBundle:
    text: str
    sources_used: List[str]
    hits_vector: int
    hits_wiki: int
    notion_used: bool


def build_context(
    query: str,
    allowed_sensitivity: Optional[List[str]] = None,
    max_chars: int = 4000,
    vector_top_k: int = 5,
    wiki_top_k: int = 2,
) -> ContextBundle:
    """Bygg minneskontext för aktuell task-fråga."""
    sources: List[str] = []
    parts: List[str] = []
    hits_vec = 0
    hits_wiki = 0
    notion_used = False

    # 1. Vektorminne
    store = MemoryStore()
    if store.enabled:
        hits = store.search(
            query_text=query,
            match_count=vector_top_k,
            allowed_sensitivity=allowed_sensitivity,
        )
        hits_vec = len(hits)
        if hits:
            sources.append("pgvector")
            block = "\n".join(h.to_context_line() for h in hits)
            parts.append(f"### Relevant historik (semantiskt minne)\n{block}")

    # 2. Notion Control Room
    room = NotionControlRoom()
    db_ids = {
        "Beslutslogg": os.environ.get("NOTION_DB_BESLUTSLOGG", "").strip(),
        "Initiativ": os.environ.get("NOTION_DB_INITIATIV", "").strip(),
        "Inkomst-radar": os.environ.get("NOTION_DB_RADAR", "").strip(),
    }
    if room.enabled and any(db_ids.values()):
        notion_brief = room.brief(db_ids, per_db=5)
        if notion_brief:
            notion_used = True
            sources.append("notion")
            parts.append(f"### Aktivt kontrollrum (Notion)\n{notion_brief}")

    # 3. Wiki (arkitektoniska beslut)
    wiki = WikiReader()
    if wiki.enabled:
        wiki_brief = wiki.brief(query, max_results=wiki_top_k)
        if wiki_brief:
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
    )
