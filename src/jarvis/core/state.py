"""JARVIS state — LangGraph MessagesState + Jarvis-fält."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState


class IntentClassification(BaseModel):
    category: Literal[
        "research", "coding", "analysis", "architecture", "casual", "strategy", "unknown"
    ] = "unknown"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    domain: Optional[str] = None


class JarvisState(MessagesState):
    current_user_id: str
    session_id: str
    intent: Optional[IntentClassification]
    active_agents: List[str]
    routing_confidence: float
    quality_score: float
    frugality: Dict[str, Any]
    memory_context: Dict[str, Any]
    approval: Optional[Dict[str, Any]]
