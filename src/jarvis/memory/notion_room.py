"""NotionControlRoom — läser Rickys Notion Control Room-databaser.

De tre databaserna (Beslutslogg, Ekosystem/Initiativ, Inkomst-radar) fungerar
som Jarvis strukturerade aktiva minne. Vi läser senaste posterna och
sammanställer en kompakt kontextbrief före varje LLM-anrop.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


@dataclass
class NotionEntry:
    title: str
    props: Dict[str, Any]
    url: str
    last_edited: str

    def to_line(self) -> str:
        # Kompakt en-radersform för prompt-injektion
        head = self.title or "(untitled)"
        extras = []
        for k in ("Kr-effekt", "Sannolikhet", "Status", "DRY_RUN", "Initiativ", "Fas"):
            v = self.props.get(k)
            if v:
                extras.append(f"{k}={v}")
        tail = " · ".join(extras)
        return f"• {head} — {tail}" if tail else f"• {head}"


class NotionControlRoom:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("NOTION_TOKEN", "")

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def query_database(self, database_id: str, page_size: int = 5) -> List[NotionEntry]:
        if not self.enabled or not database_id:
            return []
        if not (self.token.startswith("ntn_") or self.token.startswith("secret_")):
            return []
        body = {
            "page_size": page_size,
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
        }
        req = urllib.request.Request(
            f"{NOTION_API}/databases/{database_id}/query",
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
        except Exception:
            return []
        out: List[NotionEntry] = []
        for page in data.get("results", []):
            out.append(self._page_to_entry(page))
        return out

    def _page_to_entry(self, page: Dict[str, Any]) -> NotionEntry:
        props = page.get("properties", {})
        title = ""
        flat_props: Dict[str, Any] = {}
        for name, val in props.items():
            t = val.get("type")
            if t == "title":
                title = "".join(x.get("plain_text", "") for x in val.get("title", []))
            elif t == "rich_text":
                flat_props[name] = "".join(x.get("plain_text", "") for x in val.get("rich_text", []))
            elif t == "number":
                flat_props[name] = val.get("number")
            elif t == "select":
                flat_props[name] = (val.get("select") or {}).get("name")
            elif t == "multi_select":
                flat_props[name] = ", ".join(o.get("name", "") for o in val.get("multi_select", []))
            elif t == "checkbox":
                flat_props[name] = val.get("checkbox")
            elif t == "status":
                flat_props[name] = (val.get("status") or {}).get("name")
            elif t == "date":
                flat_props[name] = (val.get("date") or {}).get("start")
        return NotionEntry(
            title=title,
            props=flat_props,
            url=page.get("url", ""),
            last_edited=page.get("last_edited_time", ""),
        )

    def brief(self, database_ids: Dict[str, str], per_db: int = 5) -> str:
        """Bygger en kompakt textbrief från de tre kärndatabaserna.

        database_ids = {"Beslutslogg": "...", "Initiativ": "...", "Radar": "..."}
        """
        if not self.enabled:
            return ""
        sections: List[str] = []
        for label, db_id in database_ids.items():
            if not db_id:
                continue
            entries = self.query_database(db_id, page_size=per_db)
            if not entries:
                continue
            lines = "\n".join(e.to_line() for e in entries)
            sections.append(f"### {label} (senaste {len(entries)})\n{lines}")
        return "\n\n".join(sections)
