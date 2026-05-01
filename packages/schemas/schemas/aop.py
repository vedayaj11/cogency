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
    # PRD AC6.5 deploy gate — when `deploy=true` AND a prior eval exists for
    # this AOP with pass_rate below `deploy_pass_threshold`, the API refuses
    # to set the new version as current unless `force_deploy=true`. Forcing
    # is allowed but writes an audit_events row recording the override.
    force_deploy: bool = False
    deploy_pass_threshold: float = 0.85


class AOPCreateResponse(BaseModel):
    aop_id: UUID
    version_id: UUID
    version_number: int
    status: str  # draft|ready|deployed|deploy_blocked
    compile_errors: list[str] = []
    deploy_blocked: bool = False
    deploy_block_reason: str | None = None
    last_eval_pass_rate: float | None = None


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
    # When set, the executor uses this dict directly as the agent's case
    # context instead of looking up sf.case in the mirror. Used by the eval
    # runner so a golden_case payload feeds the AOP without needing an
    # actual Salesforce record.
    case_context_override: dict | None = None
    # Used by the eval runner to mark runs that should NOT auto-trigger
    # downstream side effects (CDC re-trigger, audit events). Eval runs
    # produce trace data but should not be confused with prod traffic.
    is_eval: bool = False


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


class EvalRunInput(BaseModel):
    tenant_id: UUID
    eval_run_id: UUID  # pre-created by the API
    dataset_id: UUID
    aop_version_id: UUID
    pass_threshold: float = 0.85


class EvalRunResult(BaseModel):
    eval_run_id: UUID
    cases_total: int
    cases_passed: int
    pass_rate: float
    aggregate_scores: dict[str, float]
    cost_usd: float
