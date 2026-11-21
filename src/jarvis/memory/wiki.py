"""WikiReader — läser Perplexity project wiki-sidor från en lokal snapshot.

Wikin är arkitektoniskt låst långtidsminne. I GitHub Actions har vi ingen
direktåtkomst till Perplexity — istället commit:as en snapshot till repo:t
under `wiki/` (kan uppdateras via schemalagd sync-workflow i Fas 3).

Sökningen är enkel: hämta sidor vars titel/beskrivning/innehåll matchar
frågeord. Passar bra för att injecera arkitektoniska beslut i systemprompten.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

WIKI_DIR = Path(__file__).resolve().parents[3] / "wiki"


@dataclass
class WikiPage:
    id: str
    title: str
    description: str
    content: str
    path: Path

    def excerpt(self, limit: int = 500) -> str:
        return self.content[:limit].strip() + ("…" if len(self.content) > limit else "")


class WikiReader:
    def __init__(self, wiki_dir: Path = WIKI_DIR):
        self.wiki_dir = wiki_dir
        self._pages: Optional[List[WikiPage]] = None

    @property
    def enabled(self) -> bool:
        return self.wiki_dir.exists() and any(self.wiki_dir.glob("**/*.md"))

    def _load(self) -> List[WikiPage]:
        if self._pages is not None:
            return self._pages
        pages: List[WikiPage] = []
        if not self.wiki_dir.exists():
            self._pages = pages
            return pages
        for md in self.wiki_dir.glob("**/*.md"):
            try:
                raw = md.read_text(encoding="utf-8")
            except Exception:
                continue
            title, desc, content = self._parse_frontmatter(raw, fallback_title=md.stem)
            pages.append(
                WikiPage(
                    id=str(md.relative_to(self.wiki_dir)).replace(".md", ""),
                    title=title,
                    description=desc,
                    content=content,
                    path=md,
                )
            )
        self._pages = pages
        return pages

    def _parse_frontmatter(self, raw: str, fallback_title: str) -> tuple[str, str, str]:
        title, desc = fallback_title, ""
        content = raw
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
        if m:
            fm, content = m.group(1), m.group(2)
            for line in fm.splitlines():
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip("\"'")
                elif line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip().strip("\"'")
        return title, desc, content.strip()

    def search(self, query: str, max_results: int = 3) -> List[WikiPage]:
        query = (query or "").lower().strip()
        if not query:
            return []
        pages = self._load()
        scored: List[tuple[float, WikiPage]] = []
        terms = [t for t in re.split(r"\s+", query) if len(t) > 2]
        if not terms:
            return []
        for p in pages:
            hay = f"{p.title}\n{p.description}\n{p.content}".lower()
            score = sum(hay.count(t) for t in terms)
            if p.title.lower() in query or query in p.title.lower():
                score += 5
            if score > 0:
                scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:max_results]]

    def brief(self, query: str, max_results: int = 3) -> str:
        pages = self.search(query, max_results=max_results)
        if not pages:
            return ""
        lines = []
        for p in pages:
            lines.append(f"### {p.title}\n{p.description}\n\n{p.excerpt(600)}")
        return "\n\n".join(lines)
