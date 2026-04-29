"""Agent inbox endpoints (PRD §6.5).

Read:
    GET /v1/inbox?status=pending

Actions (each writes an audit_events row + updates recommended_action.decision):
    POST /v1/inbox/{id}/approve   {reason?: str}
    POST /v1/inbox/{id}/reject    {reason: str}
    POST /v1/inbox/{id}/take_over {reason?: str}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.aop import AgentInboxItem, AuditEvent

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


# ---------- actions ----------

class InboxActionRequest(BaseModel):
    reason: str | None = None


class InboxActionResponse(BaseModel):
    id: UUID
    status: str


_ACTION_TO_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "take_over": "taken_over",
}


async def _apply_action(
    *,
    item_id: UUID,
    action: str,
    payload: InboxActionRequest,
    settings: Settings,
    session: AsyncSession,
) -> InboxActionResponse:
    target_status = _ACTION_TO_STATUS[action]

    item = await session.get(AgentInboxItem, item_id)
    if item is None:
        raise HTTPException(404, f"inbox item {item_id} not found")
    if item.tenant_id != settings.cogency_dev_tenant_id:
        raise HTTPException(404, "inbox item not in this tenant")
    if item.status != "pending":
        raise HTTPException(
            409, f"inbox item already in terminal state '{item.status}'"
        )

    if action == "reject" and not payload.reason:
        raise HTTPException(400, "reason is required when rejecting an inbox item")

    decision = {
        "action": action,
        "by": "human:dev_user",  # TODO(auth): wire to authenticated user
        "at": datetime.now(UTC).isoformat(),
        "reason": payload.reason,
    }
    merged_action = dict(item.recommended_action or {})
    merged_action["decision"] = decision

    before = {"status": item.status, "recommended_action": item.recommended_action}
    item.status = target_status
    item.recommended_action = merged_action
    after = {"status": item.status, "recommended_action": item.recommended_action}

    session.add(
        AuditEvent(
            tenant_id=settings.cogency_dev_tenant_id,
            actor_type="human",
            actor_id="dev_user",
            action=f"inbox.{action}",
            target_type="agent_inbox_item",
            target_id=str(item.id),
            before=before,
            after=after,
        )
    )
    await session.commit()
    return InboxActionResponse(id=item.id, status=target_status)


@router.post("/v1/inbox/{item_id}/approve", response_model=InboxActionResponse)
async def approve(
    item_id: UUID,
    payload: InboxActionRequest = InboxActionRequest(),
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> InboxActionResponse:
    return await _apply_action(
        item_id=item_id, action="approve", payload=payload, settings=settings, session=session
    )


@router.post("/v1/inbox/{item_id}/reject", response_model=InboxActionResponse)
async def reject(
    item_id: UUID,
    payload: InboxActionRequest,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> InboxActionResponse:
    return await _apply_action(
        item_id=item_id, action="reject", payload=payload, settings=settings, session=session
    )


@router.post("/v1/inbox/{item_id}/take_over", response_model=InboxActionResponse)
async def take_over(
    item_id: UUID,
    payload: InboxActionRequest = InboxActionRequest(),
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> InboxActionResponse:
    return await _apply_action(
        item_id=item_id, action="take_over", payload=payload, settings=settings, session=session
    )
