"""Read tools — case-centric.

All read against the local mirror (sub-100ms). Marked `is_read_only=True` so
the executor dispatches them in parallel when the LLM emits multiple in one
turn.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import desc, or_, select

from db.models.sf import (
    SfCase,
    SfCaseComment,
    SfContact,
    SfEmailMessage,
)

from tools.registry import Tool, ToolContext


# ---------- list_cases ----------

class ListCasesInput(BaseModel):
    status: str | None = Field(default=None, description="Exact Case.Status filter.")
    priority: str | None = None
    contact_id: str | None = None
    account_id: str | None = None
    owner_id: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class ListCasesItem(BaseModel):
    id: str
    case_number: str | None
    subject: str | None
    status: str | None
    priority: str | None
    contact_id: str | None
    account_id: str | None
    system_modstamp: datetime


class ListCasesOutput(BaseModel):
    items: list[ListCasesItem]
    total_returned: int


async def list_cases(ctx: ToolContext, p: ListCasesInput) -> ListCasesOutput:
    if ctx.session is None:
        raise RuntimeError("list_cases requires a DB session")
    stmt = select(SfCase).where(
        SfCase.org_id == ctx.tenant_id, SfCase.is_deleted.is_(False)
    )
    if p.status:
        stmt = stmt.where(SfCase.status == p.status)
    if p.priority:
        stmt = stmt.where(SfCase.priority == p.priority)
    if p.contact_id:
        stmt = stmt.where(SfCase.contact_id == p.contact_id)
    if p.account_id:
        stmt = stmt.where(SfCase.account_id == p.account_id)
    if p.owner_id:
        stmt = stmt.where(SfCase.owner_id == p.owner_id)
    stmt = stmt.order_by(desc(SfCase.system_modstamp)).limit(p.limit)
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return ListCasesOutput(
        items=[
            ListCasesItem(
                id=r.id,
                case_number=r.case_number,
                subject=r.subject,
                status=r.status,
                priority=r.priority,
                contact_id=r.contact_id,
                account_id=r.account_id,
                system_modstamp=r.system_modstamp,
            )
            for r in rows
        ],
        total_returned=len(rows),
    )


LIST_CASES = Tool(
    name="list_cases",
    description="List cases from the local mirror filtered by status / priority / contact / account / owner. Use to scan inbound queues or find related work.",
    required_scopes=["case.read"],
    input_schema=ListCasesInput,
    output_schema=ListCasesOutput,
    func=list_cases,
    is_read_only=True,
)


# ---------- search_cases ----------

class SearchCasesInput(BaseModel):
    query: str = Field(description="Free-text query against subject + description.")
    limit: int = Field(default=10, ge=1, le=50)


class SearchCasesOutput(BaseModel):
    items: list[ListCasesItem]


async def search_cases(ctx: ToolContext, p: SearchCasesInput) -> SearchCasesOutput:
    if ctx.session is None:
        raise RuntimeError("search_cases requires a DB session")
    like = f"%{p.query}%"
    stmt = (
        select(SfCase)
        .where(
            SfCase.org_id == ctx.tenant_id,
            SfCase.is_deleted.is_(False),
            or_(
                SfCase.subject.ilike(like),
                SfCase.description.ilike(like),
                SfCase.case_number.ilike(like),
            ),
        )
        .order_by(desc(SfCase.system_modstamp))
        .limit(p.limit)
    )
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return SearchCasesOutput(
        items=[
            ListCasesItem(
                id=r.id,
                case_number=r.case_number,
                subject=r.subject,
                status=r.status,
                priority=r.priority,
                contact_id=r.contact_id,
                account_id=r.account_id,
                system_modstamp=r.system_modstamp,
            )
            for r in rows
        ]
    )


SEARCH_CASES = Tool(
    name="search_cases",
    description="Free-text search over case subject + description + number. Returns recent matches. (Semantic search lands in M7 once embeddings are populated.)",
    required_scopes=["case.read"],
    input_schema=SearchCasesInput,
    output_schema=SearchCasesOutput,
    func=search_cases,
    is_read_only=True,
)


# ---------- list_case_comments ----------

class ListCaseCommentsInput(BaseModel):
    case_id: str
    limit: int = Field(default=50, ge=1, le=200)


class CommentItem(BaseModel):
    id: str
    body: str | None
    is_published: bool
    created_by_id: str | None
    created_date: datetime | None


class ListCaseCommentsOutput(BaseModel):
    items: list[CommentItem]


async def list_case_comments(
    ctx: ToolContext, p: ListCaseCommentsInput
) -> ListCaseCommentsOutput:
    if ctx.session is None:
        raise RuntimeError("list_case_comments requires a DB session")
    stmt = (
        select(SfCaseComment)
        .where(
            SfCaseComment.org_id == ctx.tenant_id,
            SfCaseComment.parent_id == p.case_id,
            SfCaseComment.is_deleted.is_(False),
        )
        .order_by(desc(SfCaseComment.created_date))
        .limit(p.limit)
    )
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return ListCaseCommentsOutput(
        items=[
            CommentItem(
                id=r.id,
                body=r.comment_body,
                is_published=r.is_published,
                created_by_id=r.created_by_id,
                created_date=r.created_date,
            )
            for r in rows
        ]
    )


LIST_CASE_COMMENTS = Tool(
    name="list_case_comments",
    description="Read every comment (internal + customer-facing) on a Case from the local mirror, newest first.",
    required_scopes=["case.read"],
    input_schema=ListCaseCommentsInput,
    output_schema=ListCaseCommentsOutput,
    func=list_case_comments,
    is_read_only=True,
)


# ---------- list_case_emails ----------

class ListCaseEmailsInput(BaseModel):
    case_id: str
    limit: int = Field(default=50, ge=1, le=200)


class EmailItem(BaseModel):
    id: str
    incoming: bool
    from_address: str | None
    to_address: str | None
    subject: str | None
    text_body: str | None
    status: str | None
    message_date: datetime | None


class ListCaseEmailsOutput(BaseModel):
    items: list[EmailItem]


async def list_case_emails(
    ctx: ToolContext, p: ListCaseEmailsInput
) -> ListCaseEmailsOutput:
    if ctx.session is None:
        raise RuntimeError("list_case_emails requires a DB session")
    stmt = (
        select(SfEmailMessage)
        .where(
            SfEmailMessage.org_id == ctx.tenant_id,
            SfEmailMessage.parent_id == p.case_id,
            SfEmailMessage.is_deleted.is_(False),
        )
        .order_by(desc(SfEmailMessage.message_date))
        .limit(p.limit)
    )
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return ListCaseEmailsOutput(
        items=[
            EmailItem(
                id=r.id,
                incoming=r.incoming,
                from_address=r.from_address,
                to_address=r.to_address,
                subject=r.subject,
                text_body=r.text_body,
                status=r.status,
                message_date=r.message_date,
            )
            for r in rows
        ]
    )


LIST_CASE_EMAILS = Tool(
    name="list_case_emails",
    description="Read the email thread on a Case from the local mirror, newest first. Returns inbound + outbound messages with bodies.",
    required_scopes=["case.read"],
    input_schema=ListCaseEmailsInput,
    output_schema=ListCaseEmailsOutput,
    func=list_case_emails,
    is_read_only=True,
)


# ---------- get_case_history ----------

class GetCaseHistoryInput(BaseModel):
    case_id: str
    limit_per_kind: int = Field(default=50, ge=1, le=200)


class HistoryEntry(BaseModel):
    kind: Literal["comment", "email", "case_modstamp"]
    at: datetime | None
    summary: str
    extra: dict[str, Any] = {}


class GetCaseHistoryOutput(BaseModel):
    entries: list[HistoryEntry]


async def get_case_history(
    ctx: ToolContext, p: GetCaseHistoryInput
) -> GetCaseHistoryOutput:
    """Aggregate comments + emails + the case's own modstamp into a single
    chronological feed. The agent uses this to ground a reply in everything
    that's happened on the case."""
    if ctx.session is None:
        raise RuntimeError("get_case_history requires a DB session")

    case = (
        await ctx.session.execute(
            select(SfCase).where(
                SfCase.org_id == ctx.tenant_id, SfCase.id == p.case_id
            )
        )
    ).scalar_one_or_none()
    entries: list[HistoryEntry] = []
    if case is not None:
        entries.append(
            HistoryEntry(
                kind="case_modstamp",
                at=case.system_modstamp,
                summary=f"Case {case.case_number or p.case_id} status={case.status}",
                extra={"status": case.status, "priority": case.priority},
            )
        )

    comments_stmt = (
        select(SfCaseComment)
        .where(
            SfCaseComment.org_id == ctx.tenant_id,
            SfCaseComment.parent_id == p.case_id,
        )
        .order_by(desc(SfCaseComment.created_date))
        .limit(p.limit_per_kind)
    )
    for c in (await ctx.session.execute(comments_stmt)).scalars().all():
        entries.append(
            HistoryEntry(
                kind="comment",
                at=c.created_date,
                summary=(c.comment_body or "")[:200],
                extra={
                    "is_published": c.is_published,
                    "created_by_id": c.created_by_id,
                },
            )
        )

    emails_stmt = (
        select(SfEmailMessage)
        .where(
            SfEmailMessage.org_id == ctx.tenant_id,
            SfEmailMessage.parent_id == p.case_id,
        )
        .order_by(desc(SfEmailMessage.message_date))
        .limit(p.limit_per_kind)
    )
    for e in (await ctx.session.execute(emails_stmt)).scalars().all():
        direction = "inbound" if e.incoming else "outbound"
        entries.append(
            HistoryEntry(
                kind="email",
                at=e.message_date,
                summary=f"{direction} — {e.subject or '(no subject)'}",
                extra={
                    "from": e.from_address,
                    "to": e.to_address,
                    "body_preview": (e.text_body or "")[:200],
                },
            )
        )

    entries.sort(key=lambda x: x.at or datetime.min, reverse=True)
    return GetCaseHistoryOutput(entries=entries)


GET_CASE_HISTORY = Tool(
    name="get_case_history",
    description="Aggregate the full timeline (case status changes, comments, emails) for a single case in chronological order. The first thing to call when investigating a case.",
    required_scopes=["case.read"],
    input_schema=GetCaseHistoryInput,
    output_schema=GetCaseHistoryOutput,
    func=get_case_history,
    is_read_only=True,
)


# ---------- list_related_cases ----------

class ListRelatedCasesInput(BaseModel):
    case_id: str
    by: Literal["contact", "account"] = "contact"
    limit: int = Field(default=10, ge=1, le=50)


class ListRelatedCasesOutput(BaseModel):
    items: list[ListCasesItem]


async def list_related_cases(
    ctx: ToolContext, p: ListRelatedCasesInput
) -> ListRelatedCasesOutput:
    if ctx.session is None:
        raise RuntimeError("list_related_cases requires a DB session")
    case = (
        await ctx.session.execute(
            select(SfCase).where(
                SfCase.org_id == ctx.tenant_id, SfCase.id == p.case_id
            )
        )
    ).scalar_one_or_none()
    if case is None:
        return ListRelatedCasesOutput(items=[])

    join_field = case.contact_id if p.by == "contact" else case.account_id
    if not join_field:
        return ListRelatedCasesOutput(items=[])

    pred = (
        SfCase.contact_id == join_field
        if p.by == "contact"
        else SfCase.account_id == join_field
    )
    stmt = (
        select(SfCase)
        .where(
            SfCase.org_id == ctx.tenant_id,
            SfCase.id != p.case_id,
            pred,
        )
        .order_by(desc(SfCase.system_modstamp))
        .limit(p.limit)
    )
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return ListRelatedCasesOutput(
        items=[
            ListCasesItem(
                id=r.id,
                case_number=r.case_number,
                subject=r.subject,
                status=r.status,
                priority=r.priority,
                contact_id=r.contact_id,
                account_id=r.account_id,
                system_modstamp=r.system_modstamp,
            )
            for r in rows
        ]
    )


LIST_RELATED_CASES = Tool(
    name="list_related_cases",
    description="Find prior cases on the same contact or account. Use to detect repeat issues, escalation patterns, or to compare a customer's history before deciding.",
    required_scopes=["case.read"],
    input_schema=ListRelatedCasesInput,
    output_schema=ListRelatedCasesOutput,
    func=list_related_cases,
    is_read_only=True,
)


# ---------- get_case_metrics ----------

class GetCaseMetricsInput(BaseModel):
    case_id: str


class GetCaseMetricsOutput(BaseModel):
    case_id: str
    age_seconds: int | None
    last_touch_seconds: int | None
    comment_count: int
    email_count: int
    is_open: bool


async def get_case_metrics(
    ctx: ToolContext, p: GetCaseMetricsInput
) -> GetCaseMetricsOutput:
    if ctx.session is None:
        raise RuntimeError("get_case_metrics requires a DB session")
    case = (
        await ctx.session.execute(
            select(SfCase).where(
                SfCase.org_id == ctx.tenant_id, SfCase.id == p.case_id
            )
        )
    ).scalar_one_or_none()
    if case is None:
        return GetCaseMetricsOutput(
            case_id=p.case_id,
            age_seconds=None,
            last_touch_seconds=None,
            comment_count=0,
            email_count=0,
            is_open=False,
        )

    from datetime import UTC

    now = datetime.now(UTC)

    def _seconds_since(dt: datetime | None) -> int | None:
        if dt is None:
            return None
        # Coerce naive→UTC to avoid the case timezone trap.
        if dt.tzinfo is None:
            from datetime import UTC as _UTC

            dt = dt.replace(tzinfo=_UTC)
        return int((now - dt).total_seconds())

    comment_count = len(
        (
            await ctx.session.execute(
                select(SfCaseComment.id).where(
                    SfCaseComment.org_id == ctx.tenant_id,
                    SfCaseComment.parent_id == p.case_id,
                )
            )
        ).all()
    )
    email_count = len(
        (
            await ctx.session.execute(
                select(SfEmailMessage.id).where(
                    SfEmailMessage.org_id == ctx.tenant_id,
                    SfEmailMessage.parent_id == p.case_id,
                )
            )
        ).all()
    )
    return GetCaseMetricsOutput(
        case_id=case.id,
        age_seconds=_seconds_since(case.created_date),
        last_touch_seconds=_seconds_since(case.system_modstamp),
        comment_count=comment_count,
        email_count=email_count,
        is_open=(case.status or "").lower() not in {"closed", "resolved"},
    )


GET_CASE_METRICS = Tool(
    name="get_case_metrics",
    description="Compute SLA-relevant metrics for a Case: age, time since last touch, comment/email counts, open/closed flag.",
    required_scopes=["case.read"],
    input_schema=GetCaseMetricsInput,
    output_schema=GetCaseMetricsOutput,
    func=get_case_metrics,
    is_read_only=True,
)


__all__ = [
    "LIST_CASES",
    "SEARCH_CASES",
    "LIST_CASE_COMMENTS",
    "LIST_CASE_EMAILS",
    "GET_CASE_HISTORY",
    "LIST_RELATED_CASES",
    "GET_CASE_METRICS",
]
