"""Email tools.

`draft_email_reply` produces a structured proposal with no side effect — the
agent uses it to think about what to say without consuming SF API quota.
`send_email_reply` actually sends via Salesforce — gated by default.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from salesforce import OutboxWriter

from tools.registry import Tool, ToolContext


# ---------- draft_email_reply ----------

class DraftEmailReplyInput(BaseModel):
    case_id: str
    to_address: str
    subject: str
    body: str = Field(description="Plain-text or HTML body for the proposed reply.")
    rationale: str = Field(description="One-sentence justification grounded in case context.")


class DraftEmailReplyOutput(BaseModel):
    proposed: bool = True
    case_id: str
    to_address: str
    subject: str
    body: str
    rationale: str


async def draft_email_reply(
    ctx: ToolContext, p: DraftEmailReplyInput
) -> DraftEmailReplyOutput:
    """No side effect — proposal only. The agent should call this before
    `send_email_reply` so the trace shows the proposed body."""
    return DraftEmailReplyOutput(
        case_id=p.case_id,
        to_address=p.to_address,
        subject=p.subject,
        body=p.body,
        rationale=p.rationale,
    )


DRAFT_EMAIL_REPLY = Tool(
    name="draft_email_reply",
    description="Compose a proposed email reply to the customer. Side-effect-free; produces a structured draft the agent can review and then send.",
    required_scopes=["email.draft"],
    input_schema=DraftEmailReplyInput,
    output_schema=DraftEmailReplyOutput,
    func=draft_email_reply,
    is_read_only=True,  # no side effects
)


# ---------- send_email_reply ----------

class SendEmailReplyInput(BaseModel):
    case_id: str
    to_address: str
    subject: str
    text_body: str
    html_body: str | None = None


class SendEmailReplyOutput(BaseModel):
    succeeded: bool
    email_message_id: str | None = None
    error: str | None = None


async def send_email_reply(
    ctx: ToolContext, p: SendEmailReplyInput
) -> SendEmailReplyOutput:
    """Send an outbound EmailMessage tied to the case via SF outbox."""
    if ctx.sf_client is None:
        return SendEmailReplyOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    fields = {
        "ParentId": p.case_id,
        "ToAddress": p.to_address,
        "Subject": p.subject,
        "TextBody": p.text_body,
        "HtmlBody": p.html_body,
        "Status": "3",  # Sent (Salesforce email status enum)
        "Incoming": False,
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    outcomes = await writer.composite_upsert("EmailMessage", [fields])
    if not outcomes:
        return SendEmailReplyOutput(succeeded=False, error="empty outcome")
    out = outcomes[0]
    return SendEmailReplyOutput(
        succeeded=out.succeeded,
        email_message_id=out.record_id or None,
        error=out.error,
    )


SEND_EMAIL_REPLY = Tool(
    name="send_email_reply",
    description="Send an outbound email reply attached to the Case. High-stakes — gated by default; an inbox approval re-fires the action.",
    required_scopes=["email.send"],
    input_schema=SendEmailReplyInput,
    output_schema=SendEmailReplyOutput,
    func=send_email_reply,
    requires_approval=True,
)


__all__ = ["DRAFT_EMAIL_REPLY", "SEND_EMAIL_REPLY"]
