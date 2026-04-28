"""End-to-end executor test with a mocked LLM and in-memory tool registry.

Exercises:
- Tool dispatch loop with multiple tool calls in one response
- Guardrail evaluation (requires_approval_if + halt_on)
- Cost rollup across multiple LLM completions
- Failure path when a step's input fails Pydantic validation
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from agents.aop_executor import AOPExecutor
from agents.llm import LLMResponse, TokenUsage, ToolCall
from aop import AOP, Guardrail, Step
from tools import Registry, Tool, ToolContext


pytestmark = pytest.mark.asyncio


class FakeLLM:
    """LLMClient stub that replays a queue of pre-baked LLMResponses."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if not self.responses:
            raise RuntimeError("FakeLLM ran out of responses")
        return self.responses.pop(0)


class _NoopIn(BaseModel):
    case_id: str
    amount_usd: float
    reason: str


class _NoopOut(BaseModel):
    proposed: bool = True
    case_id: str
    amount_usd: float
    reason: str
    requires_approval: bool


async def _propose_refund(_ctx: ToolContext, payload: _NoopIn) -> _NoopOut:
    return _NoopOut(
        case_id=payload.case_id,
        amount_usd=payload.amount_usd,
        reason=payload.reason,
        requires_approval=payload.amount_usd > 500,
    )


def _build_registry() -> Registry:
    return Registry().extend(
        [
            Tool(
                name="propose_refund",
                description="Test refund tool",
                required_scopes=["refund.propose"],
                input_schema=_NoopIn,
                output_schema=_NoopOut,
                func=_propose_refund,
            )
        ]
    )


def _build_aop(*, with_guardrail: bool) -> AOP:
    guardrails = (
        [
            Guardrail(
                kind="requires_approval_if",
                expr="refund_amount > 500",
                message="exceeds $500",
            )
        ]
        if with_guardrail
        else []
    )
    return AOP(
        name="test_refund",
        description="Issue a refund.",
        steps=[
            Step(
                name="propose",
                tool="propose_refund",
                required_scopes=["refund.propose"],
            )
        ],
        guardrails=guardrails,
        body="Call propose_refund and emit a final summary.",
    )


def _llm_response(
    *,
    text: str = "",
    tool_calls: list[ToolCall] | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> LLMResponse:
    usage = TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cost_usd=0.001,
    )
    return LLMResponse(
        text=text,
        tool_calls=tool_calls or [],
        usage=usage,
        finish_reason="stop" if not tool_calls else "tool_calls",
    )


async def _run(executor: AOPExecutor, aop: AOP) -> Any:
    return await executor.run(
        aop=aop,
        case_context={"case_id": "C-001"},
        tool_context=ToolContext(tenant_id=uuid4(), case_id="C-001"),
        granted_scopes=["refund.propose"],
        aop_version_id=str(uuid4()),
        case_id="C-001",
    )


async def test_resolved_path_below_guardrail_threshold():
    fake = FakeLLM(
        [
            _llm_response(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="propose_refund",
                        arguments={
                            "case_id": "C-001",
                            "amount_usd": 100,
                            "reason": "broken widget",
                        },
                    )
                ]
            ),
            _llm_response(text="Refund of $100 proposed for broken widget."),
        ]
    )
    executor = AOPExecutor(llm=fake, registry=_build_registry())
    outcome = await _run(executor, _build_aop(with_guardrail=True))
    assert outcome.status == "resolved"
    assert any(s.tool_name == "propose_refund" for s in outcome.steps)
    assert outcome.token_in == 200  # two LLM calls × 100 prompt tokens
    assert outcome.cost_usd > 0


async def test_escalates_when_guardrail_fires():
    fake = FakeLLM(
        [
            _llm_response(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="propose_refund",
                        arguments={
                            "case_id": "C-001",
                            "amount_usd": 750,
                            "reason": "lost shipment",
                        },
                    )
                ]
            )
            # No second response — guardrail should short-circuit
        ]
    )
    executor = AOPExecutor(llm=fake, registry=_build_registry())
    outcome = await _run(executor, _build_aop(with_guardrail=True))
    assert outcome.status == "escalated_human"
    assert outcome.steps[-1].tool_name == "(guardrail)"
    assert "exceeds" in (outcome.steps[-1].error or "").lower() or "approval" in (
        outcome.steps[-1].error or ""
    ).lower()


async def test_records_failure_when_tool_input_invalid():
    fake = FakeLLM(
        [
            _llm_response(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="propose_refund",
                        arguments={"case_id": "C-001", "reason": "missing amount"},
                    )
                ]
            ),
            _llm_response(text="Could not propose a refund — input was malformed."),
        ]
    )
    executor = AOPExecutor(llm=fake, registry=_build_registry())
    outcome = await _run(executor, _build_aop(with_guardrail=False))
    failed_step = next(s for s in outcome.steps if s.tool_name == "propose_refund")
    assert failed_step.status == "failed"
    assert failed_step.error
    assert outcome.status == "resolved"  # final message after the failure


async def test_unknown_scope_blocks_tool():
    fake = FakeLLM(
        [
            _llm_response(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="propose_refund",
                        arguments={
                            "case_id": "C-001",
                            "amount_usd": 50,
                            "reason": "x",
                        },
                    )
                ]
            ),
            _llm_response(text="cannot proceed"),
        ]
    )
    executor = AOPExecutor(llm=fake, registry=_build_registry())
    outcome = await executor.run(
        aop=_build_aop(with_guardrail=False),
        case_context={"case_id": "C-001"},
        tool_context=ToolContext(tenant_id=uuid4(), case_id="C-001"),
        granted_scopes=[],  # propose_refund requires refund.propose; not granted
        aop_version_id=str(uuid4()),
        case_id="C-001",
    )
    failed = next(s for s in outcome.steps if s.tool_name == "propose_refund")
    assert failed.status == "failed"
    assert "missing scopes" in (failed.error or "").lower()
