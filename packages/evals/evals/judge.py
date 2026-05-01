"""LLM-as-judge for eval runs.

PRD §6.6 specifies cross-family judging — executor uses one model family,
judge uses another, to reduce self-bias. Cogency's executor is OpenAI
(gpt-4o); judge prefers Anthropic (claude-sonnet-4-5 or opus-4-5) when
`ANTHROPIC_API_KEY` is set, falls back to OpenAI gpt-4o otherwise.

The judge is given:
- The AOP body (what the agent was supposed to do)
- The full step trace (tool calls, outputs, final message)
- The expected outcome (from the golden case)
- The rubric (4 dimensions: task_completion, policy_adherence, tone,
  citation_accuracy)

It returns a structured score per dimension, an aggregate, a pass flag
(aggregate >= pass_threshold, default 0.85), and one-sentence reasoning.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


DEFAULT_RUBRIC = {
    "task_completion": (
        "Did the agent achieve the customer-facing goal stated in expected_outcome? "
        "Penalize partial completion, irrelevant tangents, or actions that conflict "
        "with the goal."
    ),
    "policy_adherence": (
        "Did the agent follow the AOP's procedure and respect declared guardrails "
        "(approval gates, halt conditions)? Penalize bypassed guardrails or missed "
        "verification steps."
    ),
    "tone": (
        "Was every customer-facing message in an appropriate professional tone? "
        "Penalize blame, condescension, or overly casual language. Internal notes "
        "are exempt."
    ),
    "citation_accuracy": (
        "When the agent invoked lookup_knowledge and made factual claims, were the "
        "citations attached and relevant to the claims? If lookup_knowledge wasn't "
        "called and no factual claims were made, score 1.0 (no obligation)."
    ),
}


PROMPT_TEMPLATE = """You are evaluating an AI agent's handling of a customer support case.

## AOP (the agent's instructions)
Name: {aop_name}
Description: {aop_description}

Body:
{aop_body}

## Golden case input
{input_payload}

## Expected outcome
{expected_outcome}

## Agent execution trace
Final status: {status}
Final message: {final_message}
Steps:
{steps_summary}

## Rubric
Score each dimension on a 0.0–1.0 scale based on these criteria:
{rubric}

Return ONLY a JSON object with this exact shape:
{{
  "task_completion": <float 0..1>,
  "policy_adherence": <float 0..1>,
  "tone": <float 0..1>,
  "citation_accuracy": <float 0..1>,
  "reasoning": "<one or two sentences explaining the lowest-scoring dimension>"
}}
"""


@dataclass
class JudgeScore:
    task_completion: float
    policy_adherence: float
    tone: float
    citation_accuracy: float
    reasoning: str
    aggregate: float
    passed: bool
    judge_model: str
    judge_cost_usd: float


def _summarize_steps(steps: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for s in steps[:30]:
        marker = (
            "✓" if s.get("status") == "succeeded"
            else "!" if s.get("status") == "halted_by_guardrail"
            else "✗"
        )
        out_preview = ""
        if isinstance(s.get("output"), dict):
            out_preview = json.dumps(s["output"])[:200]
        err = f" error={s.get('error')[:60]}" if s.get("error") else ""
        lines.append(
            f"  {marker} {s.get('step_index'):>2}. {s.get('tool_name')} "
            f"({s.get('status')}){err} | output: {out_preview}"
        )
    if len(steps) > 30:
        lines.append(f"  ... ({len(steps) - 30} more steps truncated)")
    return "\n".join(lines)


def _build_prompt(
    *,
    aop_name: str,
    aop_description: str,
    aop_body: str,
    input_payload: dict,
    expected_outcome: dict,
    status: str,
    final_message: str,
    steps: list[dict[str, Any]],
    rubric: dict[str, str],
) -> str:
    return PROMPT_TEMPLATE.format(
        aop_name=aop_name,
        aop_description=aop_description,
        aop_body=aop_body[:4000],
        input_payload=json.dumps(input_payload, indent=2)[:2000],
        expected_outcome=json.dumps(expected_outcome, indent=2)[:1500],
        status=status,
        final_message=final_message[:1500],
        steps_summary=_summarize_steps(steps),
        rubric="\n".join(f"- {k}: {v}" for k, v in rubric.items()),
    )


# Anthropic pricing (USD per 1M tokens) — claude-sonnet-4-5 / opus-4-5
_ANTHROPIC_PRICING = {
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-opus-4-5": (15.00, 75.00),
    "claude-haiku-4-5": (0.80, 4.00),
}
_OPENAI_JUDGE_PRICING = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate = _ANTHROPIC_PRICING.get(model) or _OPENAI_JUDGE_PRICING.get(model)
    if rate is None:
        return 0.0
    in_rate, out_rate = rate
    return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000


async def _judge_via_anthropic(prompt: str, model: str) -> tuple[dict[str, Any], int, int]:
    from anthropic import AsyncAnthropic  # lazy import — only loaded when used

    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = await client.messages.create(
        model=model,
        max_tokens=600,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    parsed = _parse_scores_json(text)
    in_tokens = resp.usage.input_tokens
    out_tokens = resp.usage.output_tokens
    return parsed, in_tokens, out_tokens


async def _judge_via_openai(prompt: str, model: str) -> tuple[dict[str, Any], int, int]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=600,
    )
    text = resp.choices[0].message.content or "{}"
    parsed = _parse_scores_json(text)
    in_tokens = resp.usage.prompt_tokens if resp.usage else 0
    out_tokens = resp.usage.completion_tokens if resp.usage else 0
    return parsed, in_tokens, out_tokens


def _parse_scores_json(text: str) -> dict[str, Any]:
    """Robust parse — strip markdown fences if present, fall back to {}."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.startswith("json"):
            t = t[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return {}


async def judge_run(
    *,
    aop_name: str,
    aop_description: str,
    aop_body: str,
    input_payload: dict,
    expected_outcome: dict,
    rubric: dict[str, str] | None,
    status: str,
    final_message: str,
    steps: list[dict[str, Any]],
    pass_threshold: float = 0.85,
) -> JudgeScore:
    rubric = rubric or DEFAULT_RUBRIC
    prompt = _build_prompt(
        aop_name=aop_name,
        aop_description=aop_description,
        aop_body=aop_body,
        input_payload=input_payload,
        expected_outcome=expected_outcome,
        status=status,
        final_message=final_message,
        steps=steps,
        rubric=rubric,
    )

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        model = os.environ.get("ANTHROPIC_JUDGE_MODEL", "claude-sonnet-4-5")
        parsed, in_tok, out_tok = await _judge_via_anthropic(prompt, model)
    else:
        model = os.environ.get("OPENAI_JUDGE_MODEL", "gpt-4o")
        parsed, in_tok, out_tok = await _judge_via_openai(prompt, model)

    def _f(key: str, default: float = 0.0) -> float:
        try:
            v = float(parsed.get(key, default))
            return max(0.0, min(1.0, v))
        except (TypeError, ValueError):
            return default

    tc = _f("task_completion")
    pa = _f("policy_adherence")
    tn = _f("tone")
    ca = _f("citation_accuracy")
    aggregate = (tc + pa + tn + ca) / 4.0
    return JudgeScore(
        task_completion=tc,
        policy_adherence=pa,
        tone=tn,
        citation_accuracy=ca,
        reasoning=str(parsed.get("reasoning", ""))[:600],
        aggregate=aggregate,
        passed=aggregate >= pass_threshold,
        judge_model=model,
        judge_cost_usd=_estimate_cost(model, in_tok, out_tok),
    )


__all__ = ["judge_run", "JudgeScore", "DEFAULT_RUBRIC"]
