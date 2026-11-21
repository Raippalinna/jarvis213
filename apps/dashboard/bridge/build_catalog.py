"""Normalize the observed connector inventory without credentials or private contents."""
import json
import sys
from pathlib import Path
from policy import READ_TOOLS, ALIASES, LOCKED

inventory = json.loads(Path(sys.argv[1]).read_text())
requested = set(READ_TOOLS) | set(ALIASES) | set(LOCKED)
connectors = []
for connector in inventory["connectors"]:
    source = connector["source_id"]
    if source not in requested:
        continue
    target = ALIASES.get(source, source)
    available = {t["name"] for t in connector["tools"]}
    connectors.append({
        "source_id": source, "name": connector["name"], "status": connector["status"],
        "read_tools": [t for t in READ_TOOLS.get(target, []) if t in available or target != source],
        "note": LOCKED.get(source, "Gemensam filsökning" if source in ALIASES else ""),
    })
Path(__file__).with_name("catalog.json").write_text(json.dumps({
    "at": "2026-09-29T14:50:00Z",
    "connectors": sorted(connectors, key=lambda c: c["name"].casefold()),
}, ensure_ascii=False, indent=2))
print(f"Catalog created: {len(connectors)} sources, no credentials.")
