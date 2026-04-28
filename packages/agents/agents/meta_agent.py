"""Meta-agent — selects which AOP to run for a given case.

PRD AC4.1: emits {selected_aop_id, confidence, reasoning, fallback_aop_id}.
PRD AC4.2: confidence below tenant threshold (default 0.7) routes to human.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetaAgentSelection(BaseModel):
    selected_aop_id: str | None
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    fallback_aop_id: str | None = None
    route_to_human: bool = False
