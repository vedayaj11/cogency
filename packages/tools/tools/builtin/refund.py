"""Refund proposal tool — produces a structured refund payload, no side effects.

Actual refund issuance lives in a separate tool (not in MVP) that calls the
billing system. This tool exists so the AOP can express "decide on a refund"
distinctly from "issue the refund" — useful for guardrails like
`requires_approval_if(refund_amount > 500)`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tools.registry import Tool, ToolContext


class ProposeRefundInput(BaseModel):
    case_id: str
    amount_usd: float = Field(ge=0, description="Refund amount in USD.")
    reason: str = Field(description="One-sentence justification grounded in policy.")


class ProposeRefundOutput(BaseModel):
    proposed: bool = True
    case_id: str
    amount_usd: float
    reason: str
    requires_approval: bool


async def propose_refund(
    ctx: ToolContext, payload: ProposeRefundInput
) -> ProposeRefundOutput:
    return ProposeRefundOutput(
        case_id=payload.case_id,
        amount_usd=payload.amount_usd,
        reason=payload.reason,
        requires_approval=payload.amount_usd > 500,
    )


PROPOSE_REFUND = Tool(
    name="propose_refund",
    description="Propose a refund for the case. Does not issue the refund — only emits a structured proposal which the AOP guardrails will gate on amount.",
    required_scopes=["refund.propose"],
    input_schema=ProposeRefundInput,
    output_schema=ProposeRefundOutput,
    func=propose_refund,
)
