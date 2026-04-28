"""Sync workflow contracts shared between API and worker."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BackfillCasesInput(BaseModel):
    tenant_id: UUID
    since: datetime | None = None
    soql_extra_where: str | None = None


class BackfillCasesResult(BaseModel):
    job_id: str
    rows_applied: int
    watermark_ts: datetime | None = None
