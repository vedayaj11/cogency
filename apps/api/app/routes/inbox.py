"""Agent inbox endpoints (PRD §6.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.aop import AgentInboxItem

from app.config import Settings
from app.deps import db_session, settings_dep

router = APIRouter()


class InboxItem(BaseModel):
    id: UUID
    case_id: str
    escalation_reason: str
    recommended_action: dict[str, Any] | None
    confidence: float | None
    status: str
    sla_deadline: datetime | None
    created_at: datetime


class InboxResponse(BaseModel):
    items: list[InboxItem]


@router.get("/v1/inbox", response_model=InboxResponse)
async def list_inbox(
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
    status: str | None = Query(default="pending"),
    limit: int = Query(default=100, ge=1, le=500),
) -> InboxResponse:
    stmt = select(AgentInboxItem).where(
        AgentInboxItem.tenant_id == settings.cogency_dev_tenant_id
    )
    if status:
        stmt = stmt.where(AgentInboxItem.status == status)
    stmt = stmt.order_by(desc(AgentInboxItem.created_at)).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    return InboxResponse(
        items=[
            InboxItem(
                id=r.id,
                case_id=r.case_id,
                escalation_reason=r.escalation_reason,
                recommended_action=r.recommended_action,
                confidence=r.confidence,
                status=r.status,
                sla_deadline=r.sla_deadline,
                created_at=r.created_at,
            )
            for r in rows
        ]
    )
