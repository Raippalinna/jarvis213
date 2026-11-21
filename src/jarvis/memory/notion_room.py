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


def format_log_line(ts: str, title: str, body: str, limit: int = 350) -> str:
    """Komprimerar ett loggblock till en rad: hoppar header (Task/Tier/Kvalitet) och tar svaret."""
    answer = body.split("---", 1)[1].strip() if "---" in body else body
    answer = " ".join(answer.split())[:limit]
    return f"• {ts} · {title[:70]} → {answer}"


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

    def recent_log(self, page_id: str, hours: int = 48, max_items: int = 5) -> List[str]:
        """Senaste Jarvis-körningarna som toggle-block på Control Room-sidan.

        Varje körning postas som toggle 'JARVIS · <UTC-tid> · <task>'. Vi läser
        blockbarnen, väljer de som är nyare än `hours` och hämtar första
        textstycket ur varje (max `max_items` extra anrop). Det är den enda
        källa som säger vad Jarvis faktiskt gjorde igår.
        """
        if not self.enabled or not page_id:
            return []
        if not (self.token.startswith("ntn_") or self.token.startswith("secret_")):
            return []
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        toggles: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        for _ in range(10):  # max 1000 block
            url = f"{NOTION_API}/blocks/{page_id}/children?page_size=100"
            if cursor:
                url += f"&start_cursor={cursor}"
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers=self._headers()), timeout=15
                ) as r:
                    data = json.loads(r.read())
            except Exception:
                break
            for b in data.get("results", []):
                if b.get("type") != "toggle":
                    continue
                title = "".join(x.get("plain_text", "") for x in b["toggle"].get("rich_text", []))
                if not title.startswith("JARVIS"):
                    continue
                try:
                    ts = datetime.fromisoformat(str(b.get("created_time", "")).replace("Z", "+00:00"))
                except Exception:
                    continue
                if ts >= cutoff:
                    toggles.append({"id": b["id"], "title": title, "ts": ts})
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        toggles.sort(key=lambda t: t["ts"], reverse=True)
        lines: List[str] = []
        for t in toggles[:max_items]:
            body = ""
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(
                        f"{NOTION_API}/blocks/{t['id']}/children?page_size=3", headers=self._headers()
                    ), timeout=15,
                ) as r:
                    kids = json.loads(r.read()).get("results", [])
                for k in kids:
                    if k.get("type") == "paragraph":
                        body = "".join(x.get("plain_text", "") for x in k["paragraph"].get("rich_text", []))
                        break
            except Exception:
                pass
            lines.append(format_log_line(t["ts"].strftime("%Y-%m-%d %H:%M UTC"), t["title"], body))
        return lines

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
