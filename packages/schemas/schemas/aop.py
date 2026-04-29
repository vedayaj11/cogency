"""AOP authoring + run contracts shared between API and worker."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AOPCreateRequest(BaseModel):
    name: str
    source_md: str
    deploy: bool = False  # mark new version as the current version


class AOPCreateResponse(BaseModel):
    aop_id: UUID
    version_id: UUID
    version_number: int
    status: str  # draft|deployed
    compile_errors: list[str] = []


class RunAOPInput(BaseModel):
    tenant_id: UUID
    aop_version_id: UUID
    case_id: str
    # Pre-created run row; activity adopts it instead of creating a fresh one.
    # The API endpoint creates the row so the response can carry the canonical
    # cogency run_id (the Temporal workflow run_id is internal and unstable).
    run_id: UUID | None = None
    granted_scopes: list[str] = [
        "case.read",
        "case.update",
        "contact.read",
        "refund.propose",
    ]


class RunAOPResult(BaseModel):
    run_id: UUID
    status: str
    cost_usd: float
    token_in: int
    token_out: int
    step_count: int


class AOPRunSummary(BaseModel):
    id: UUID
    aop_version_id: UUID
    case_id: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    cost_usd: float
    token_in: int
    token_out: int
    trace_id: str | None
    steps: list[dict[str, Any]] = []
