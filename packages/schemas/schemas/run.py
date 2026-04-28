from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AOPStepResult(BaseModel):
    step_index: int
    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    reasoning: str | None = None
    status: Literal["pending", "running", "succeeded", "failed", "halted_by_guardrail"] = "pending"
    latency_ms: int | None = None
    cost_usd: float | None = None
    error: str | None = None


class AOPRunOutcome(BaseModel):
    run_id: str
    aop_version_id: str
    case_id: str
    status: Literal["resolved", "escalated_human", "failed", "cancelled"]
    started_at: datetime
    ended_at: datetime
    steps: list[AOPStepResult] = Field(default_factory=list)
    cost_usd: float
    token_in: int
    token_out: int
    trace_id: str
