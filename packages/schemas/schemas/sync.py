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
