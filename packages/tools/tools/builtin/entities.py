"""Read tools — entity-centric (Account / Contact)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from db.models.sf import SfAccount, SfCase, SfContact

from tools.registry import Tool, ToolContext


# ---------- list_contact_cases ----------

class ListContactCasesInput(BaseModel):
    contact_id: str
    open_only: bool = True
    limit: int = Field(default=20, ge=1, le=100)


class ContactCaseItem(BaseModel):
    id: str
    case_number: str | None
    subject: str | None
    status: str | None
    priority: str | None
    system_modstamp: datetime


class ListContactCasesOutput(BaseModel):
    items: list[ContactCaseItem]


async def list_contact_cases(
    ctx: ToolContext, p: ListContactCasesInput
) -> ListContactCasesOutput:
    if ctx.session is None:
        raise RuntimeError("list_contact_cases requires a DB session")
    stmt = select(SfCase).where(
        SfCase.org_id == ctx.tenant_id,
        SfCase.contact_id == p.contact_id,
        SfCase.is_deleted.is_(False),
    )
    if p.open_only:
        stmt = stmt.where(SfCase.status.notin_(("Closed", "Resolved")))
    stmt = stmt.order_by(desc(SfCase.system_modstamp)).limit(p.limit)
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return ListContactCasesOutput(
        items=[
            ContactCaseItem(
                id=r.id,
                case_number=r.case_number,
                subject=r.subject,
                status=r.status,
                priority=r.priority,
                system_modstamp=r.system_modstamp,
            )
            for r in rows
        ]
    )


LIST_CONTACT_CASES = Tool(
    name="list_contact_cases",
    description="Read all cases on a single Contact, newest first. Filter to open-only by default.",
    required_scopes=["case.read", "contact.read"],
    input_schema=ListContactCasesInput,
    output_schema=ListContactCasesOutput,
    func=list_contact_cases,
    is_read_only=True,
)


# ---------- get_account ----------

class GetAccountInput(BaseModel):
    account_id: str


class GetAccountOutput(BaseModel):
    found: bool
    account_id: str
    name: str | None = None
    custom_fields: dict[str, Any] = {}


async def get_account(ctx: ToolContext, p: GetAccountInput) -> GetAccountOutput:
    if ctx.session is None:
        raise RuntimeError("get_account requires a DB session")
    row = (
        await ctx.session.execute(
            select(SfAccount).where(
                SfAccount.org_id == ctx.tenant_id, SfAccount.id == p.account_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return GetAccountOutput(found=False, account_id=p.account_id)
    return GetAccountOutput(
        found=True,
        account_id=row.id,
        name=row.name,
        custom_fields=row.custom_fields or {},
    )


GET_ACCOUNT = Tool(
    name="get_account",
    description="Read an Account from the local mirror by Id.",
    required_scopes=["account.read"],
    input_schema=GetAccountInput,
    output_schema=GetAccountOutput,
    func=get_account,
    is_read_only=True,
)


# ---------- list_account_cases ----------

class ListAccountCasesInput(BaseModel):
    account_id: str
    open_only: bool = True
    limit: int = Field(default=20, ge=1, le=100)


async def list_account_cases(
    ctx: ToolContext, p: ListAccountCasesInput
) -> ListContactCasesOutput:
    if ctx.session is None:
        raise RuntimeError("list_account_cases requires a DB session")
    stmt = select(SfCase).where(
        SfCase.org_id == ctx.tenant_id,
        SfCase.account_id == p.account_id,
        SfCase.is_deleted.is_(False),
    )
    if p.open_only:
        stmt = stmt.where(SfCase.status.notin_(("Closed", "Resolved")))
    stmt = stmt.order_by(desc(SfCase.system_modstamp)).limit(p.limit)
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return ListContactCasesOutput(
        items=[
            ContactCaseItem(
                id=r.id,
                case_number=r.case_number,
                subject=r.subject,
                status=r.status,
                priority=r.priority,
                system_modstamp=r.system_modstamp,
            )
            for r in rows
        ]
    )


LIST_ACCOUNT_CASES = Tool(
    name="list_account_cases",
    description="Read all cases on a single Account.",
    required_scopes=["case.read", "account.read"],
    input_schema=ListAccountCasesInput,
    output_schema=ListContactCasesOutput,
    func=list_account_cases,
    is_read_only=True,
)


# ---------- get_account_health ----------

class GetAccountHealthInput(BaseModel):
    account_id: str


class GetAccountHealthOutput(BaseModel):
    account_id: str
    open_case_count: int
    closed_30d_count: int
    open_high_priority_count: int
    contacts_count: int
    last_activity_at: datetime | None


async def get_account_health(
    ctx: ToolContext, p: GetAccountHealthInput
) -> GetAccountHealthOutput:
    if ctx.session is None:
        raise RuntimeError("get_account_health requires a DB session")

    open_count = (
        await ctx.session.execute(
            select(func.count())
            .select_from(SfCase)
            .where(
                SfCase.org_id == ctx.tenant_id,
                SfCase.account_id == p.account_id,
                SfCase.status.notin_(("Closed", "Resolved")),
            )
        )
    ).scalar_one() or 0

    high_pri_count = (
        await ctx.session.execute(
            select(func.count())
            .select_from(SfCase)
            .where(
                SfCase.org_id == ctx.tenant_id,
                SfCase.account_id == p.account_id,
                SfCase.status.notin_(("Closed", "Resolved")),
                SfCase.priority.in_(("High", "Critical", "P0", "P1")),
            )
        )
    ).scalar_one() or 0

    from datetime import UTC, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=30)
    closed_30d_count = (
        await ctx.session.execute(
            select(func.count())
            .select_from(SfCase)
            .where(
                SfCase.org_id == ctx.tenant_id,
                SfCase.account_id == p.account_id,
                SfCase.status.in_(("Closed", "Resolved")),
                SfCase.system_modstamp >= cutoff,
            )
        )
    ).scalar_one() or 0

    contacts_count = (
        await ctx.session.execute(
            select(func.count())
            .select_from(SfContact)
            .where(
                SfContact.org_id == ctx.tenant_id,
                SfContact.account_id == p.account_id,
            )
        )
    ).scalar_one() or 0

    last_activity = (
        await ctx.session.execute(
            select(func.max(SfCase.system_modstamp)).where(
                SfCase.org_id == ctx.tenant_id, SfCase.account_id == p.account_id
            )
        )
    ).scalar_one()

    return GetAccountHealthOutput(
        account_id=p.account_id,
        open_case_count=open_count,
        closed_30d_count=closed_30d_count,
        open_high_priority_count=high_pri_count,
        contacts_count=contacts_count,
        last_activity_at=last_activity,
    )


GET_ACCOUNT_HEALTH = Tool(
    name="get_account_health",
    description="Roll up an Account's case health: open count, recent closures, high-priority count, contacts, last activity. Use to gauge customer state before sensitive actions.",
    required_scopes=["case.read", "account.read", "contact.read"],
    input_schema=GetAccountHealthInput,
    output_schema=GetAccountHealthOutput,
    func=get_account_health,
    is_read_only=True,
)


__all__ = [
    "LIST_CONTACT_CASES",
    "GET_ACCOUNT",
    "LIST_ACCOUNT_CASES",
    "GET_ACCOUNT_HEALTH",
]
