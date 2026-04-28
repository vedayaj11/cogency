"""Contact lookup + identity verification tools."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select

from db.models.sf import SfCase, SfContact

from tools.registry import Tool, ToolContext


class LookupContactInput(BaseModel):
    contact_id: str


class LookupContactOutput(BaseModel):
    found: bool
    contact_id: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    account_id: str | None = None


async def lookup_contact(
    ctx: ToolContext, payload: LookupContactInput
) -> LookupContactOutput:
    if ctx.session is None:
        raise RuntimeError("lookup_contact requires a DB session")
    stmt = select(SfContact).where(
        SfContact.org_id == ctx.tenant_id, SfContact.id == payload.contact_id
    )
    contact = (await ctx.session.execute(stmt)).scalar_one_or_none()
    if contact is None:
        return LookupContactOutput(found=False, contact_id=payload.contact_id)
    return LookupContactOutput(
        found=True,
        contact_id=contact.id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        email=contact.email,
        account_id=contact.account_id,
    )


LOOKUP_CONTACT = Tool(
    name="lookup_contact",
    description="Read a Contact from the local Salesforce mirror by Id.",
    required_scopes=["contact.read"],
    input_schema=LookupContactInput,
    output_schema=LookupContactOutput,
    func=lookup_contact,
)


class VerifyIdentityInput(BaseModel):
    case_id: str
    claimed_email: str = Field(description="Email address the customer provided.")


class VerifyIdentityOutput(BaseModel):
    verified: bool
    contact_id: str | None = None
    on_file_email: str | None = None
    reason: str


async def verify_customer_identity(
    ctx: ToolContext, payload: VerifyIdentityInput
) -> VerifyIdentityOutput:
    if ctx.session is None:
        raise RuntimeError("verify_customer_identity requires a DB session")
    case_stmt = select(SfCase).where(
        SfCase.org_id == ctx.tenant_id, SfCase.id == payload.case_id
    )
    case = (await ctx.session.execute(case_stmt)).scalar_one_or_none()
    if case is None or not case.contact_id:
        return VerifyIdentityOutput(
            verified=False, reason="case not found or has no related contact"
        )
    contact_stmt = select(SfContact).where(
        SfContact.org_id == ctx.tenant_id, SfContact.id == case.contact_id
    )
    contact = (await ctx.session.execute(contact_stmt)).scalar_one_or_none()
    if contact is None:
        return VerifyIdentityOutput(
            verified=False, reason="related contact not in mirror yet"
        )
    on_file = (contact.email or "").lower().strip()
    claimed = payload.claimed_email.lower().strip()
    verified = bool(on_file) and on_file == claimed
    return VerifyIdentityOutput(
        verified=verified,
        contact_id=contact.id,
        on_file_email=contact.email,
        reason=(
            "email matches contact on file"
            if verified
            else "email does not match contact on file"
        ),
    )


VERIFY_CUSTOMER_IDENTITY = Tool(
    name="verify_customer_identity",
    description="Compare a claimed email against the email on the Case's related Contact. Returns verified=true only on exact match.",
    required_scopes=["contact.read", "case.read"],
    input_schema=VerifyIdentityInput,
    output_schema=VerifyIdentityOutput,
    func=verify_customer_identity,
)
