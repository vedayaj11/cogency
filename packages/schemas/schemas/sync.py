"""Sync workflow contracts shared between API and worker."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


# Sobjects we know how to backfill. Each maps to a (mirror table, fields,
# repository) trio at the worker side.
SObjectName = Literal[
    "Case",
    "EmailMessage",
    "CaseComment",
    "Task",
    "KnowledgeArticleVersion",
]


class BackfillCasesInput(BaseModel):
    """Backwards-compatible alias for `BackfillSObjectInput(sobject="Case")`."""

    tenant_id: UUID
    since: datetime | None = None
    soql_extra_where: str | None = None


class BackfillCasesResult(BaseModel):
    job_id: str
    rows_applied: int
    watermark_ts: datetime | None = None


class BackfillSObjectInput(BaseModel):
    """Generic per-sobject backfill request."""

    tenant_id: UUID
    sobject: SObjectName
    since: datetime | None = None
    soql_extra_where: str | None = None


class BackfillSObjectResult(BaseModel):
    sobject: str
    job_id: str
    rows_applied: int
    watermark_ts: datetime | None = None


class BackfillAllInput(BaseModel):
    tenant_id: UUID
    sobjects: list[SObjectName] = ["Case", "EmailMessage", "CaseComment", "Task"]


class BackfillAllResult(BaseModel):
    results: list[BackfillSObjectResult]


class ConsumeCaseCDCInput(BaseModel):
    """Long-running CDC consumer: subscribe to /data/CaseChangeEvent and
    optionally auto-trigger an AOP on each CREATE."""

    tenant_id: UUID
    topic: str = "/data/CaseChangeEvent"
    auto_trigger_aop: str | None = "case_manager"
    # If set, auto-trigger only fires when this AOP's current_version_id is
    # not None (i.e. someone has explicitly deployed it).
    require_deployed: bool = True
    batch_size: int = 100


class ConsumeCaseCDCResult(BaseModel):
    events_processed: int
    last_replay_id_hex: str | None
    runs_triggered: int
