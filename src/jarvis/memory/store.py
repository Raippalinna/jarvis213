"""Identity-scoped text memory.

The observed vector RPC has no identity parameters. It is deliberately not used.
Text retrieval filters the existing tenant_id AND user_id columns server-side.
Rows without verified ownership stay excluded; no implicit legacy backfill occurs.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .access import MemoryScope
from ..safety import guard
from ..safety.secrets import contains_secret


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
    sensitivity: str = "internal"

    def to_context_line(self) -> str:
        head = self.title or self.source
        return f"[{head}] (score={self.score:.2f}) {self.content[:400]}"


class MemoryStore:
    def __init__(self, supabase_url: Optional[str] = None,
                 supabase_key: Optional[str] = None):
        self.supabase_url = (supabase_url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    @property
    def enabled(self) -> bool:
        return self.supabase_url.startswith("https://") and bool(self.supabase_key)

    def _headers(self) -> Dict[str, str]:
        return {"apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json", "Prefer": "return=representation"}

    def _insert(self, row: Dict[str, Any]) -> Any:
        guard.require_autonomy("memory_write", supabase_url=self.supabase_url,
                               supabase_key=self.supabase_key)
        request = urllib.request.Request(
            f"{self.supabase_url}/rest/v1/jarvis_memory", method="POST",
            data=json.dumps(row).encode("utf-8"), headers=self._headers(),
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())

    def upsert(self, content: str, source: str, source_ref: Optional[str] = None,
               kind: str = "chunk", title: Optional[str] = None,
               metadata: Optional[Dict[str, Any]] = None,
               sensitivity: str = "internal", *, scope: Optional[MemoryScope] = None
               ) -> Optional[int]:
        if not self.enabled or scope is None or sensitivity not in scope.allowed_levels:
            return None
        if contains_secret(json.dumps([content, source_ref, title, metadata], ensure_ascii=False)):
            return None
        row = {
            "tenant_id": scope.tenant_id, "user_id": scope.user_id,
            "content": content, "source": source, "source_ref": source_ref,
            "kind": kind, "title": title, "metadata": metadata or {},
            "sensitivity": sensitivity, "embedding": None,
        }
        try:
            response = self._insert(row)
            return int(response[0]["id"]) if isinstance(response, list) and response else None
        except Exception:
            return None

    def search(self, query_text: str, match_count: int = 5,
               min_similarity: float = 0.5,
               allowed_sensitivity: Optional[List[str]] = None,
               filter_source: Optional[List[str]] = None,
               *, scope: Optional[MemoryScope] = None) -> List[MemoryHit]:
        # No embedding transmission and no call to the unscoped vector RPC.
        if not self.enabled or scope is None or not query_text.strip() or contains_secret(query_text):
            return []
        allowed = scope.allowed_levels
        if allowed_sensitivity is not None:
            allowed = [level for level in allowed if level in allowed_sensitivity]
        if not allowed:
            return []
        params = {
            "tenant_id": f"eq.{scope.tenant_id}",
            "user_id": f"eq.{scope.user_id}",
            "content": f"ilike.*{query_text[:60]}*",
            "sensitivity": "in.(" + ",".join(allowed) + ")",
            "limit": str(max(1, min(int(match_count), 50))),
            "order": "updated_at.desc",
            "select": "id,tenant_id,user_id,source,source_ref,kind,title,content,metadata,sensitivity",
        }
        if filter_source:
            params["source"] = "in.(" + ",".join(filter_source) + ")"
        request = urllib.request.Request(
            f"{self.supabase_url}/rest/v1/jarvis_memory?{urllib.parse.urlencode(params)}",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                rows = json.loads(response.read())
            if not isinstance(rows, list):
                return []
            hits = []
            for row in rows:
                # Defense in depth; the request itself already filters ownership.
                if (row.get("tenant_id") != scope.tenant_id or
                    row.get("user_id") != scope.user_id or
                    row.get("sensitivity") not in allowed or
                    contains_secret(json.dumps(row, ensure_ascii=False))):
                    continue
                hits.append(MemoryHit(
                    id=int(row["id"]), source=row["source"], source_ref=row.get("source_ref"),
                    kind=row["kind"], title=row.get("title"), content=row["content"],
                    metadata=row.get("metadata") or {}, similarity=0, text_rank=0.5,
                    score=0.5, sensitivity=row["sensitivity"],
                ))
            return hits
        except Exception:
            return []
