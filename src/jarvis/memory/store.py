"""MemoryStore — semantiskt minne i Supabase pgvector.

Skriver och läser chunks. Embeddings genereras via Comet/OpenAI-kompatibel
endpoint (text-embedding-3-small, 1536 dim). Vid nyckel-fel eller nätfel
degradar vi tyst till fulltext-only retrieval.

Regler:
- Skriver aldrig chunks med sensitivity='secret' till Supabase-tabellen.
- Vid hämtning filtreras chunks med sensitivity > taskens tier automatiskt.
- Läckageskydd: vi anropar embedding-API ENDAST på providers som INTE
  tränar på data (Comet). Aldrig Groq/Gemini för embeddings av privat text.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"   # eller anon om RLS tillåter


@dataclass
class MemoryHit:
    id: int
    source: str
    source_ref: Optional[str]
    kind: str
    title: Optional[str]
    content: str
    metadata: Dict[str, Any]
    similarity: float
    text_rank: float
    score: float

    def to_context_line(self) -> str:
        ref = f" · {self.source_ref}" if self.source_ref else ""
        head = self.title or f"{self.source}{ref}"
        return f"[{head}] (score={self.score:.2f}) {self.content[:400]}"


class MemoryStore:
    @staticmethod
    def _safe_sensitivity(values):
        """None ger standardnivåer; tomma eller ogiltiga listor nekar åtkomst."""
        permitted = ("public", "internal", "confidential")
        if values is None:
            return list(permitted)
        if not isinstance(values, (list, tuple)):
            return []
        if any(not isinstance(value, str) or value not in permitted for value in values):
            return []
        return list(dict.fromkeys(values))

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        embedding_provider_key_env: str = "COMET_API_KEY",
        embedding_base_url: str = "https://api.cometapi.com/v1",
        embedding_model: str = "text-embedding-3-small",
    ):
        self.supabase_url = supabase_url or os.environ.get(SUPABASE_URL_ENV, "").rstrip("/")
        self.supabase_key = supabase_key or os.environ.get(SUPABASE_KEY_ENV, "")
        self.emb_key = os.environ.get(embedding_provider_key_env, "")
        self.emb_base = embedding_base_url.rstrip("/")
        self.emb_model = embedding_model

    @property
    def enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    # -- Embeddings -----------------------------------------------------------

    def embed(self, text: str) -> Optional[List[float]]:
        """Returnerar embedding-vektor eller None vid fel/saknad nyckel."""
        if not self.emb_key or not text.strip():
            return None
        req = urllib.request.Request(
            f"{self.emb_base}/embeddings",
            method="POST",
            data=json.dumps({"model": self.emb_model, "input": text[:8000]}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.emb_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            return data["data"][0]["embedding"]
        except Exception:
            return None

    # -- REST-hjälpare mot Supabase ------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _post_rpc(self, fn: str, body: Dict[str, Any]) -> Any:
        if not self.supabase_url.startswith("http"):
            raise ValueError("supabase_url is not set")
        req = urllib.request.Request(
            f"{self.supabase_url}/rest/v1/rpc/{fn}",
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())

    def _insert(self, row: Dict[str, Any]) -> Any:
        if not self.supabase_url.startswith("http"):
            raise ValueError("supabase_url is not set")
        req = urllib.request.Request(
            f"{self.supabase_url}/rest/v1/jarvis_memory",
            method="POST",
            data=json.dumps(row).encode("utf-8"),
            headers=self._headers(),
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())

    # -- Publika operationer --------------------------------------------------

    def upsert(
        self,
        content: str,
        source: str,
        source_ref: Optional[str] = None,
        kind: str = "chunk",
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        sensitivity: str = "internal",
    ) -> Optional[int]:
        """Spara chunk i minnet. Returnerar id eller None vid fel."""
        if not self.enabled or not self.supabase_url.startswith("http"):
            return None
        if sensitivity == "secret":
            return None  # Aldrig secret i persistent lager
        embedding = self.embed(content)
        row = {
            "content": content,
            "source": source,
            "source_ref": source_ref,
            "kind": kind,
            "title": title,
            "metadata": metadata or {},
            "sensitivity": sensitivity,
            "embedding": embedding,
        }
        try:
            resp = self._insert(row)
            if isinstance(resp, list) and resp:
                return int(resp[0].get("id", 0)) or None
        except Exception:
            return None
        return None

    def search(
        self,
        query_text: str,
        match_count: int = 5,
        min_similarity: float = 0.5,
        allowed_sensitivity: Optional[List[str]] = None,
        filter_source: Optional[List[str]] = None,
    ) -> List[MemoryHit]:
        """Hybrid retrieval: vektor + trigram fulltext."""
        if not self.enabled or not query_text.strip():
            return []
        if not self.supabase_url.startswith("http"):
            return []
        allowed_sensitivity = self._safe_sensitivity(allowed_sensitivity)
        if not allowed_sensitivity or filter_source == []:
            return []
        embedding = self.embed(query_text)
        if embedding is None:
            # Fulltext-only fallback via direktfråga (execute_sql-liknande)
            return self._fulltext_only(query_text, match_count, allowed_sensitivity, filter_source)

        body = {
            "query_embedding": embedding,
            "query_text": query_text,
            "match_count": match_count,
            "min_similarity": min_similarity,
            "filter_sensitivity": allowed_sensitivity,
        }
        if filter_source:
            body["filter_source"] = filter_source

        try:
            rows = self._post_rpc("jarvis_memory_search", body)
        except Exception:
            return []
        return [
            MemoryHit(
                id=int(r["id"]),
                source=r["source"],
                source_ref=r.get("source_ref"),
                kind=r["kind"],
                title=r.get("title"),
                content=r["content"],
                metadata=r.get("metadata") or {},
                similarity=float(r.get("similarity") or 0),
                text_rank=float(r.get("text_rank") or 0),
                score=float(r.get("score") or 0),
            )
            for r in (rows or [])
        ]

    def _fulltext_only(
        self,
        query_text: str,
        match_count: int,
        allowed_sensitivity: Optional[List[str]],
        filter_source: Optional[List[str]],
    ) -> List[MemoryHit]:
        """Fallback när embedding-API är otillgängligt: enkel PostgREST-fråga."""
        if not self.enabled:
            return []
        allowed_sensitivity = self._safe_sensitivity(allowed_sensitivity)
        if not allowed_sensitivity or filter_source == []:
            return []
        # PostgREST kräver URL-kodning av query och filter
        import urllib.parse
        safe_q = urllib.parse.quote(query_text[:60], safe="")
        params = [f"content=ilike.*{safe_q}*"]
        if allowed_sensitivity:
            in_list = ",".join(f'"{s}"' for s in allowed_sensitivity)
            params.append("sensitivity=" + urllib.parse.quote(f"in.({in_list})", safe=""))
        if filter_source:
            in_list = ",".join(
                '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
                for s in filter_source
            )
            params.append("source=" + urllib.parse.quote(f"in.({in_list})", safe=""))
        params.append(f"limit={match_count}")
        params.append("order=updated_at.desc")
        url = f"{self.supabase_url}/rest/v1/jarvis_memory?{'&'.join(params)}"
        if not url.startswith("http"):
            return []
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                rows = json.loads(r.read())
        except Exception:
            return []
        return [
            MemoryHit(
                id=int(r["id"]),
                source=r["source"],
                source_ref=r.get("source_ref"),
                kind=r["kind"],
                title=r.get("title"),
                content=r["content"],
                metadata=r.get("metadata") or {},
                similarity=0.0,
                text_rank=0.5,
                score=0.5,
            )
            for r in (rows or [])
        ]
