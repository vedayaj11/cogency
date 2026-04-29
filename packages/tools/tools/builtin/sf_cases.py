"""Case-scoped tools: read from local mirror, write back via SF outbox."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from db.models.sf import SfCase
from salesforce import OutboxWriter

from tools.registry import Tool, ToolContext


class LookupCaseInput(BaseModel):
    case_id: str = Field(description="Salesforce 18-character Case Id")


class LookupCaseOutput(BaseModel):
    found: bool
    case_id: str
    case_number: str | None = None
    subject: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    contact_id: str | None = None
    account_id: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


async def lookup_case(ctx: ToolContext, payload: LookupCaseInput) -> LookupCaseOutput:
    if ctx.session is None:
        raise RuntimeError("lookup_case requires a DB session in ToolContext")
    stmt = select(SfCase).where(
        SfCase.org_id == ctx.tenant_id, SfCase.id == payload.case_id
    )
    case = (await ctx.session.execute(stmt)).scalar_one_or_none()
    if case is None:
        return LookupCaseOutput(found=False, case_id=payload.case_id)
    return LookupCaseOutput(
        found=True,
        case_id=case.id,
        case_number=case.case_number,
        subject=case.subject,
        description=case.description,
        status=case.status,
        priority=case.priority,
        contact_id=case.contact_id,
        account_id=case.account_id,
        custom_fields=case.custom_fields or {},
    )


LOOKUP_CASE = Tool(
    name="lookup_case",
    description="Read a Case from the local Salesforce mirror by Id. Returns subject, description, status, priority, related contact/account, and custom fields.",
    required_scopes=["case.read"],
    input_schema=LookupCaseInput,
    output_schema=LookupCaseOutput,
    func=lookup_case,
    is_read_only=True,
)


class AddCaseCommentInput(BaseModel):
    case_id: str
    body: str = Field(description="Comment body. Plain text or HTML.")
    is_public: bool = Field(default=False, description="Visible to the customer if true.")


class AddCaseCommentOutput(BaseModel):
    succeeded: bool
    comment_id: str | None = None
    error: str | None = None


async def add_case_comment(
    ctx: ToolContext, payload: AddCaseCommentInput
) -> AddCaseCommentOutput:
    if ctx.sf_client is None:
        return AddCaseCommentOutput(
            succeeded=False, error="no Salesforce client in ToolContext"
        )
    writer = OutboxWriter(client=ctx.sf_client)
    outcomes = await writer.composite_upsert(
        "CaseComment",
        [
            {
                "ParentId": payload.case_id,
                "CommentBody": payload.body,
                "IsPublished": payload.is_public,
            }
        ],
    )
    if not outcomes:
        return AddCaseCommentOutput(succeeded=False, error="empty outcome")
    out = outcomes[0]
    return AddCaseCommentOutput(
        succeeded=out.succeeded, comment_id=out.record_id or None, error=out.error
    )


ADD_CASE_COMMENT = Tool(
    name="add_case_comment",
    description="Append a comment to the Case in Salesforce. Use to record reasoning or customer-facing replies.",
    required_scopes=["case.update"],
    input_schema=AddCaseCommentInput,
    output_schema=AddCaseCommentOutput,
    func=add_case_comment,
)


class UpdateCaseStatusInput(BaseModel):
    case_id: str
    status: str = Field(description="Target Case Status picklist value.")


class UpdateCaseStatusOutput(BaseModel):
    succeeded: bool
    conflict: bool = False
    error: str | None = None


async def update_case_status(
    ctx: ToolContext, payload: UpdateCaseStatusInput
) -> UpdateCaseStatusOutput:
    if ctx.sf_client is None:
        return UpdateCaseStatusOutput(
            succeeded=False, error="no Salesforce client in ToolContext"
        )
    writer = OutboxWriter(client=ctx.sf_client)
    outcome = await writer.patch_record(
        "Case", payload.case_id, {"Status": payload.status}
    )
    return UpdateCaseStatusOutput(
        succeeded=outcome.succeeded,
        conflict=outcome.conflict,
        error=outcome.error,
    )


UPDATE_CASE_STATUS = Tool(
    name="update_case_status",
    description="Update Case.Status in Salesforce. Use only after the resolution is complete.",
    required_scopes=["case.update"],
    input_schema=UpdateCaseStatusInput,
    output_schema=UpdateCaseStatusOutput,
    func=update_case_status,
)
