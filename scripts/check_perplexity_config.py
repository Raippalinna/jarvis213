"""Offline checks of reviewed Perplexity instruction text, never a settings writer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


# Observed in settings on 2026-09-22. Re-check UI before applying future changes.
TARGETS = {
    "personal_instructions": ("user", 1500),
    "brain_instructions": ("user", 1500),
    "project_instructions": ("project", 8000),
    "project_summary_instructions": ("project", 2000),
}
DEFAULT_MANIFEST = "docs/perplexity/config-manifest.json"


class ConfigError(ValueError):
    pass


def normalize(text: str) -> str:
    """Normalize CRLF and a file's final newline, not spaces or content."""
    return text.replace("\r\n", "\n").rstrip("\n")


def utf16_length(text: str) -> int:
    # HTML maxlength uses UTF-16 code units, not Python Unicode code points.
    return len(text.encode("utf-16-le")) // 2


def validate_text(field_id: str, text: str) -> str:
    if not isinstance(text, str):
        raise ConfigError(f"{field_id}: text must be a string")
    text = normalize(text)
    if not text.strip():
        raise ConfigError(f"{field_id}: empty text")
    try:
        size = utf16_length(text)
    except UnicodeError:
        raise ConfigError(f"{field_id}: invalid Unicode") from None
    if size > TARGETS[field_id][1]:
        raise ConfigError(f"{field_id}: exceeds observed UI limit")
    if any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise ConfigError(f"{field_id}: control character")
    if text[-1] not in ".!?":
        raise ConfigError(f"{field_id}: missing final punctuation; check truncation")
    return text


def validate(root: Path, manifest_path: Path) -> dict[str, str]:
    root = root.resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
        raise ConfigError("manifest: invalid schema version")
    if data["schema_version"] != 1 or set(data) != {"schema_version", "purpose", "fields"}:
        raise ConfigError("manifest: unsupported schema or fields")
    if not isinstance(data["purpose"], str) or not data["purpose"].strip():
        raise ConfigError("manifest: missing purpose")
    if not isinstance(data["fields"], list):
        raise ConfigError("manifest: fields must be a list")
    texts = {}
    seen_paths = set()
    for field in data["fields"]:
        if not isinstance(field, dict) or set(field) != {"id", "scope", "path"}:
            raise ConfigError("manifest: invalid field shape")
        field_id = field["id"]
        if not isinstance(field_id, str) or field_id not in TARGETS:
            raise ConfigError("manifest: unknown field id")
        if field_id in texts:
            raise ConfigError(f"{field_id}: duplicate id")
        if field["scope"] != TARGETS[field_id][0]:
            raise ConfigError(f"{field_id}: wrong scope")
        if not isinstance(field["path"], str) or not field["path"]:
            raise ConfigError(f"{field_id}: missing path")
        relative = Path(field["path"])
        if relative.is_absolute():
            raise ConfigError(f"{field_id}: absolute path not allowed")
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ConfigError(f"{field_id}: path missing or outside root")
        if path in seen_paths:
            raise ConfigError(f"{field_id}: duplicate file")
        seen_paths.add(path)
        texts[field_id] = validate_text(field_id, path.read_text(encoding="utf-8"))
    if set(texts) != set(TARGETS):
        raise ConfigError("manifest: incomplete target set")
    return texts


def compare_observed(texts: dict[str, str], observed: object) -> list[str]:
    """Compare supplied readback only; do not authenticate or fetch remote state."""
    if not isinstance(observed, dict) or set(observed) != set(texts):
        raise ConfigError("readback: exact target set required")
    if any(not isinstance(value, str) for value in observed.values()):
        raise ConfigError("readback: values must be strings")
    return sorted(key for key in texts if texts[key] != normalize(observed[key]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--observed", type=Path, help="Optional locally exported UI readback JSON.")
    args = parser.parse_args(argv)
    try:
        texts = validate(args.root, args.root / DEFAULT_MANIFEST)
        rows = [
            {"id": key, "utf16_length": utf16_length(value),
             "limit": TARGETS[key][1], "sha256": hashlib.sha256(value.encode()).hexdigest()}
            for key, value in texts.items()
        ]
        drift = None
        if args.observed:
            drift = compare_observed(texts, json.loads(args.observed.read_text(encoding="utf-8")))
        print(json.dumps({
            "status": "readback_differs" if drift else "offline_valid",
            "remote_state_verified": False,
            "fields": rows,
            "provided_readback_differences": drift,
        }, ensure_ascii=False, indent=2))
        return 1 if drift else 0
    except (ConfigError, OSError, ValueError, UnicodeError):
        # Avoid echoing file contents or malformed input, which may contain private data.
        print(json.dumps({"status": "invalid", "remote_state_verified": False,
                          "error": "Configuration or supplied readback failed validation."}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
