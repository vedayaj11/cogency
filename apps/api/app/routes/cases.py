"""Case list + detail endpoints driving the Workspace UI.

PRD §10.1:
    GET    /v1/cases?filters
    GET    /v1/cases/:id

Reads come from the local Salesforce mirror (`sf.case`) for sub-100ms latency;
writes (not in this milestone) flow through the SF outbox.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.aop import AOPRun
from db.models.sf import SfCase, SfContact

from app.config import Settings
from app.deps import db_session, settings_dep

router = APIRouter()


class CaseListItem(BaseModel):
    id: str
    case_number: str | None
    subject: str | None
    status: str | None
    priority: str | None
    contact_id: str | None
    system_modstamp: datetime
    has_runs: bool


class CaseListResponse(BaseModel):
    items: list[CaseListItem]
    total: int


class CaseRunSummary(BaseModel):
    id: str
    aop_version_id: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    cost_usd: float


class CaseDetail(BaseModel):
    id: str
    case_number: str | None
    subject: str | None
    description: str | None
    status: str | None
    priority: str | None
    origin: str | None
    contact_id: str | None
    account_id: str | None
    custom_fields: dict[str, Any]
    created_date: datetime | None
    system_modstamp: datetime

    contact: dict[str, Any] | None = None
    runs: list[CaseRunSummary] = []


@router.get("/v1/cases", response_model=CaseListResponse)
async def list_cases(
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
    q: str | None = Query(default=None, description="Filter by subject/case_number"),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CaseListResponse:
    base = select(SfCase).where(
        SfCase.org_id == settings.cogency_dev_tenant_id,
        SfCase.is_deleted.is_(False),
    )
    if status:
        base = base.where(SfCase.status == status)
    if q:
        like = f"%{q}%"
        base = base.where(
            or_(
                SfCase.subject.ilike(like),
                SfCase.case_number.ilike(like),
                SfCase.description.ilike(like),
            )
        )

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    stmt = base.order_by(desc(SfCase.system_modstamp)).limit(limit).offset(offset)
    rows = list((await session.execute(stmt)).scalars().all())

    if rows:
        run_count_stmt = (
            select(AOPRun.case_id, func.count(AOPRun.id))
            .where(
                AOPRun.tenant_id == settings.cogency_dev_tenant_id,
                AOPRun.case_id.in_([c.id for c in rows]),
            )
            .group_by(AOPRun.case_id)
        )
        run_counts = {
            cid: cnt for cid, cnt in (await session.execute(run_count_stmt)).all()
        }
    else:
        run_counts = {}

    return CaseListResponse(
        items=[
            CaseListItem(
                id=c.id,
                case_number=c.case_number,
                subject=c.subject,
                status=c.status,
                priority=c.priority,
                contact_id=c.contact_id,
                system_modstamp=c.system_modstamp,
                has_runs=run_counts.get(c.id, 0) > 0,
            )
            for c in rows
        ],
        total=total,
    )


@router.get("/v1/cases/{case_id}", response_model=CaseDetail)
async def get_case(
    case_id: str,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> CaseDetail:
    case = (
        await session.execute(
            select(SfCase).where(
                SfCase.org_id == settings.cogency_dev_tenant_id, SfCase.id == case_id
            )
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(404, f"case {case_id} not found in mirror")

    contact_row: dict[str, Any] | None = None
    if case.contact_id:
        contact = (
            await session.execute(
                select(SfContact).where(
                    SfContact.org_id == settings.cogency_dev_tenant_id,
                    SfContact.id == case.contact_id,
                )
            )
        ).scalar_one_or_none()
        if contact is not None:
            contact_row = {
                "id": contact.id,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "email": contact.email,
                "account_id": contact.account_id,
            }

    runs = list(
        (
            await session.execute(
                select(AOPRun)
                .where(
                    AOPRun.tenant_id == settings.cogency_dev_tenant_id,
                    AOPRun.case_id == case_id,
                )
                .order_by(desc(AOPRun.started_at))
                .limit(20)
            )
        ).scalars().all()
    )

    return CaseDetail(
        id=case.id,
        case_number=case.case_number,
        subject=case.subject,
        description=case.description,
        status=case.status,
        priority=case.priority,
        origin=case.origin,
        contact_id=case.contact_id,
        account_id=case.account_id,
        custom_fields=case.custom_fields or {},
        created_date=case.created_date,
        system_modstamp=case.system_modstamp,
        contact=contact_row,
        runs=[
            CaseRunSummary(
                id=str(r.id),
                aop_version_id=str(r.aop_version_id),
                status=r.status,
                started_at=r.started_at,
                ended_at=r.ended_at,
                cost_usd=float(r.cost_usd or 0),
            )
            for r in runs
        ],
    )
