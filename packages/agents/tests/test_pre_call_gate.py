"""Pre-call approval gate tests.

Covers:
- A tool with `requires_approval=True` halts the run before invocation,
  records an `awaiting_approval` step carrying the proposed args, and
  returns `status=escalated_human`.
- A `requires_approval_if` AOP guardrail matching on tool inputs (e.g.
  `add_case_comment.is_public == true`) halts pre-call.
- A `halt_on` guardrail still works on tool *output* (post-result path).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import BaseModel

from agents.aop_executor import AOPExecutor
from agents.llm import LLMResponse, TokenUsage, ToolCall
from aop import AOP, Guardrail, Step
from tools import Registry, Tool, ToolContext


pytestmark = pytest.mark.asyncio


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    async def complete(self, messages, **kwargs):
        if not self.responses:
            raise RuntimeError("FakeLLM exhausted")
        return self.responses.pop(0)


def _llm_resp(*, text="", tool_calls=None, prompt=100, completion=20):
    return LLMResponse(
        text=text,
        tool_calls=tool_calls or [],
        usage=TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
            cost_usd=0.001,
        ),
        finish_reason="tool_calls" if tool_calls else "stop",
    )


# ---------- fixture tools ----------

class _SendIn(BaseModel):
    case_id: str
    body: str


class _SendOut(BaseModel):
    succeeded: bool


class _CommentIn(BaseModel):
    case_id: str
    body: str
    is_public: bool = False


class _CommentOut(BaseModel):
    succeeded: bool = True


async def _send_email(_ctx: ToolContext, p: _SendIn) -> _SendOut:
    return _SendOut(succeeded=True)


async def _add_comment(_ctx: ToolContext, p: _CommentIn) -> _CommentOut:
    return _CommentOut()


def _registry() -> Registry:
    return Registry().extend(
        [
            Tool(
                name="send_email_reply",
                description="send",
                required_scopes=["email.send"],
                input_schema=_SendIn,
                output_schema=_SendOut,
                func=_send_email,
                requires_approval=True,
            ),
            Tool(
                name="add_case_comment",
                description="comment",
                required_scopes=["case.update"],
                input_schema=_CommentIn,
                output_schema=_CommentOut,
                func=_add_comment,
            ),
        ]
    )


def _aop(*, with_public_guard: bool = False) -> AOP:
    guardrails = []
    if with_public_guard:
        guardrails.append(
            Guardrail(
                kind="requires_approval_if",
                expr='add_case_comment.is_public == true',
                message="external-facing comment must be approved",
            )
        )
    return AOP(
        name="t",
        description="t",
        steps=[],
        guardrails=guardrails,
        body="test",
    )


async def _run(executor, aop, scopes):
    return await executor.run(
        aop=aop,
        case_context={"case_id": "C1"},
        tool_context=ToolContext(tenant_id=uuid4(), case_id="C1"),
        granted_scopes=scopes,
        aop_version_id=str(uuid4()),
        case_id="C1",
    )


# ---------- tests ----------

async def test_tool_requires_approval_halts_and_records_proposed():
    fake = FakeLLM(
        [
            _llm_resp(
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="send_email_reply",
                        arguments={"case_id": "C1", "body": "hi"},
                    )
                ]
            )
        ]
    )
    out = await _run(
        AOPExecutor(llm=fake, registry=_registry()),
        _aop(),
        ["email.send", "case.update"],
    )
    assert out.status == "escalated_human"
    assert out.steps[-1].tool_name == "send_email_reply"
    assert out.steps[-1].status == "halted_by_guardrail"
    # The proposed args MUST be recorded in `input` so the inbox approve
    # endpoint can re-fire them.
    assert out.steps[-1].input == {"case_id": "C1", "body": "hi"}
    # And the awaiting_approval marker MUST be in `output` so the activity
    # picks it up for inbox creation.
    assert out.steps[-1].output.get("awaiting_approval") is True


async def test_aop_guardrail_on_tool_input_halts_pre_call():
    fake = FakeLLM(
        [
            _llm_resp(
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="add_case_comment",
                        arguments={
                            "case_id": "C1",
                            "body": "External-facing reply",
                            "is_public": True,
                        },
                    )
                ]
            )
        ]
    )
    out = await _run(
        AOPExecutor(llm=fake, registry=_registry()),
        _aop(with_public_guard=True),
        ["case.update"],
    )
    assert out.status == "escalated_human"
    last = out.steps[-1]
    assert last.tool_name == "add_case_comment"
    assert last.input["is_public"] is True


async def test_internal_only_comment_passes_pre_call_gate():
    """is_public=False should NOT trip the requires_approval_if guardrail."""
    fake = FakeLLM(
        [
            _llm_resp(
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="add_case_comment",
                        arguments={
                            "case_id": "C1",
                            "body": "Internal note",
                            "is_public": False,
                        },
                    )
                ]
            ),
            _llm_resp(text="done"),
        ]
    )
    out = await _run(
        AOPExecutor(llm=fake, registry=_registry()),
        _aop(with_public_guard=True),
        ["case.update"],
    )
    assert out.status == "resolved"
    assert any(s.tool_name == "add_case_comment" and s.status == "succeeded" for s in out.steps)
