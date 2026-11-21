"""build_context — samlar minnesfragment från alla lager till en systemprompt.

Kombinerar:
1. pgvector-chunks (semantiskt passivt minne)
1b. Senaste minnesposterna kronologiskt (vad har hänt, oavsett likhet)
2. Notion Control Room-brief (strukturerat aktivt minne)
2b. Senaste Jarvis-körningarna på Control Room-loggsidan (48 h)
3. Wiki-utdrag (arkitektoniskt låst minne)

Returnerar även `diagnostics` så att körningen kan visa VARFÖR minnet är
tomt (t.ex. anon-nyckel utan GRANT) i stället för att modellen gissar.

Returnerar ren text som injiceras EFTER BASE_SYSTEM men FÖRE role-prompt.
Klipper till max_chars för att inte spränga token-cap.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    hits_recent: int = 0
    hits_log: int = 0
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Kort statusrad för loggar och Notion-meta, t.ex. 'pgvector=0 senaste=0 notion=nej logg=2 wiki=1 (nyckelroll=anon, minne=permission denied)'."""
        d = self.diagnostics
        tail = []
        if d.get("key_role"):
            tail.append(f"nyckelroll={d['key_role']}")
        if d.get("store_probe") and d["store_probe"] != "ok":
            tail.append(f"minne={d['store_probe']}")
        extra = f" ({', '.join(tail)})" if tail else ""
        return (
            f"pgvector={self.hits_vector} senaste={self.hits_recent} "
            f"notion={'ja' if self.notion_used else 'nej'} logg={self.hits_log} wiki={self.hits_wiki}{extra}"
        )


def build_context(
    query: str,
    allowed_sensitivity: Optional[List[str]] = None,
    max_chars: int = 4000,
    vector_top_k: int = 5,
    wiki_top_k: int = 2,
    recent_k: int = 5,
    log_hours: int = 48,
) -> ContextBundle:
    """Bygg minneskontext för aktuell task-fråga."""
    sources: List[str] = []
    parts: List[str] = []
    hits_vec = 0
    hits_wiki = 0
    hits_recent = 0
    hits_log = 0
    notion_used = False
    diagnostics: Dict[str, Any] = {}

    # 1. Vektorminne + senaste poster
    store = MemoryStore()
    if store.enabled:
        diagnostics["key_role"] = store.key_role()
        diagnostics["store_probe"] = store.probe()
        if diagnostics["store_probe"] == "ok":
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
            recent = store.recent(
                limit=recent_k,
                allowed_sensitivity=allowed_sensitivity,
                exclude_source=["wiki"],
            )
            hits_recent = len(recent)
            if recent:
                sources.append("recent")
                block = "\n".join(h.to_context_line() for h in recent)
                parts.append(f"### Senaste minnesposter (kronologiskt, nyast först)\n{block}")
    else:
        diagnostics["store_probe"] = "disabled"

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
    log_page = (os.environ.get("NOTION_LOG_PAGE_ID") or os.environ.get("NOTION_PAGE_ID") or "").strip()
    if room.enabled and log_page:
        log_lines = room.recent_log(log_page, hours=log_hours, max_items=recent_k)
        hits_log = len(log_lines)
        if log_lines:
            sources.append("notion_log")
            parts.append(
                f"### Senaste Jarvis-körningar (Control Room-logg, {log_hours} h, nyast först)\n"
                + "\n".join(log_lines)
            )

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
        hits_recent=hits_recent,
        hits_log=hits_log,
        diagnostics=diagnostics,
    )
