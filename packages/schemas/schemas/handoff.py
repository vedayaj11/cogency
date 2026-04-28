from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str
    source_uri: str
    span: tuple[int, int] | None = None


class HandoffPayload(BaseModel):
    """PRD AC4.3 — structured handoff payload across AI→AI and AI→human."""

    summary: str
    completed_steps: list[str] = Field(default_factory=list)
    attempted_actions: list[dict[str, Any]] = Field(default_factory=list)
    pending_decisions: list[str] = Field(default_factory=list)
    recommended_next: str | None = None
    customer_state_snapshot: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
