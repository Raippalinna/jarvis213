"""Explicit server-configured memory scope for a trusted single-user runner.

This is NOT authentication for an Internet-facing API. Such an API must first
verify its caller and bind the deployment scope server-side.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MemoryScope:
    tenant_id: str
    user_id: str
    max_sensitivity: str = "internal"
    shared_context: bool = False

    def __post_init__(self):
        object.__setattr__(self, "tenant_id", str(UUID(self.tenant_id)))
        object.__setattr__(self, "user_id", str(UUID(self.user_id)))
        if self.max_sensitivity not in ("public", "internal", "confidential"):
            raise ValueError("Invalid memory clearance")

    @property
    def allowed_levels(self) -> list[str]:
        levels = ["public", "internal", "confidential"]
        return levels[:levels.index(self.max_sensitivity) + 1]

    @classmethod
    def for_actor(cls, actor: str) -> "MemoryScope | None":
        expected = os.environ.get("JARVIS_MEMORY_ACTOR", "").strip()
        if not expected or actor != expected:
            return None
        try:
            return cls(
                tenant_id=os.environ.get("JARVIS_MEMORY_TENANT_ID", ""),
                user_id=os.environ.get("JARVIS_MEMORY_USER_ID", ""),
                max_sensitivity=os.environ.get("JARVIS_MEMORY_MAX_SENSITIVITY", "internal"),
                shared_context=os.environ.get("JARVIS_ENABLE_SHARED_CONTEXT") == "1",
            )
        except (ValueError, TypeError):
            return None
