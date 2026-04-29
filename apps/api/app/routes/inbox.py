"""Agent inbox endpoints (PRD §6.5).

Read:
    GET /v1/inbox?status=pending

Actions (each writes an audit_events row + updates recommended_action.decision):
    POST /v1/inbox/{id}/approve   {reason?: str, refire?: bool=true}
    POST /v1/inbox/{id}/reject    {reason: str}
    POST /v1/inbox/{id}/take_over {reason?: str}

When `approve` is called and the inbox item carries a `proposed_action`
(populated by the AOP executor's pre-call gate), the endpoint optionally
re-fires the action by dispatching the proposed tool against the same
ToolContext, then writes a second audit_events row capturing the dispatch
result.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.aop import AgentInboxItem, AuditEvent
from salesforce import build_salesforce_client
from tools import ToolContext, build_default_registry

from app.config import Settings
from app.deps import db_session, settings_dep

log = logging.getLogger("cogency.api.inbox")

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
    refire: bool = True  # only used by `approve`; if False the proposed action is not dispatched


class InboxActionResponse(BaseModel):
    id: UUID
    status: str
    refired: bool = False
    refire_result: dict[str, Any] | None = None
    refire_error: str | None = None


_ACTION_TO_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "take_over": "taken_over",
}


async def _refire_proposed_action(
    *,
    item: AgentInboxItem,
    settings: Settings,
    session: AsyncSession,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """Re-fire the proposed action recorded by the executor's pre-call gate.

    Returns (refired, result_dict, error). `refired=True` means we attempted
    a dispatch (regardless of whether it succeeded). `refired=False` means
    there was no proposed_action to dispatch — that's fine (e.g. for inbox
    items from post-result guardrails).
    """
    proposed = (item.recommended_action or {}).get("proposed_action")
    if not proposed or not isinstance(proposed, dict):
        return (False, None, None)

    tool_name = proposed.get("tool")
    args = proposed.get("args") or {}
    if not tool_name:
        return (False, None, "proposed_action has no tool name")

    registry = build_default_registry()
    try:
        tool = registry.get(tool_name)
    except KeyError:
        return (True, None, f"tool '{tool_name}' not in registry")

    try:
        sf_client = build_salesforce_client(
            client_id=settings.sf_client_id,
            client_secret=settings.sf_client_secret or None,
            username=settings.sf_username or None,
            private_key_path=settings.sf_jwt_private_key_path,
            login_url=settings.sf_login_url,
            token_url=settings.sf_token_url,
            api_version=settings.sf_api_version,
        )
    except Exception as e:
        log.warning("inbox.refire.sf_client_unavailable: %s", e)
        sf_client = None

    ctx = ToolContext(
        tenant_id=settings.cogency_dev_tenant_id,
        case_id=item.case_id,
        session=session,
        sf_client=sf_client,
    )
    try:
        parsed = tool.input_schema.model_validate(args)
        result = await tool.func(ctx, parsed)
        return (True, result.model_dump(), None)
    except Exception as e:
        return (True, None, str(e))


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

    # Approve + refire: dispatch the proposed action against the live SF
    # client, then capture the dispatch result in the audit row.
    refired = False
    refire_result: dict[str, Any] | None = None
    refire_error: str | None = None
    if action == "approve" and payload.refire:
        refired, refire_result, refire_error = await _refire_proposed_action(
            item=item, settings=settings, session=session
        )

    decision = {
        "action": action,
        "by": "human:dev_user",  # TODO(auth): wire to authenticated user
        "at": datetime.now(UTC).isoformat(),
        "reason": payload.reason,
        "refired": refired,
        "refire_result": refire_result,
        "refire_error": refire_error,
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
    return InboxActionResponse(
        id=item.id,
        status=target_status,
        refired=refired,
        refire_result=refire_result,
        refire_error=refire_error,
    )


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
