from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IntakeExtraction(BaseModel):
    """PRD AC1.3 — auto-extracted fields with confidence indicators."""

    matched_contact_id: str | None = None
    matched_contact_confidence: float | None = Field(default=None, ge=0, le=1)
    unmatched: bool = False
    category: str | None = None
    priority: Literal["P0", "P1", "P2", "P3"] | None = None
    sentiment: float | None = Field(default=None, ge=-1, le=1)
    language: str | None = None
    suggested_aop_id: str | None = None
    suggested_aop_confidence: float | None = Field(default=None, ge=0, le=1)
    possible_duplicate_of: list[str] = Field(default_factory=list)
    source_spans: dict[str, list[tuple[int, int]]] = Field(default_factory=dict)


class CaseContext(BaseModel):
    """Context bundle assembled per case for meta-agent consumption."""

    case_id: str
    tenant_id: str
    subject: str
    description: str
    customer_id: str | None
    channel: Literal["email", "web_form", "sf_event", "voice_transcript"]
    created_at: datetime
    intake: IntakeExtraction
    history_summary: str | None = None
