"""AOP runtime executor.

PRD §6.2: takes a compiled AOP + case context, drives the LLM through a tool-
calling loop, captures per-step traces, enforces guardrails, and emits an
AOPRunOutcome.

Loop shape:

    system: AOP body + persona + scope contract
    user: case context (subject, description, contact, customer state)
    while step_count < max_steps:
        resp = llm.complete(messages, tools=registry.specs())
        if resp.tool_calls:
            for call in resp.tool_calls:
                result = registry.dispatch(call.name, call.args, ctx)
                append tool_call message + tool_result message
                record AOPStepResult
                evaluate guardrails(result, run_state)
                if guardrail halts: break with status=escalated_human|failed
        else:
            final answer = resp.text
            break

Cost is rolled up across every LLM call. Tools are dispatched inline within
the executor activity for MVP; promoting each tool to its own Temporal
Activity is a follow-up (PRD §8.3).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from aop import AOP, Guardrail
from schemas import AOPRunOutcome, AOPStepResult

from agents.llm import LLMClient, TokenUsage
from agents.guardrails import GuardrailViolation, evaluate_guardrails


class AOPExecutionError(Exception):
    pass


@dataclass
class ExecutorRuntimeState:
    """Mutable state visible to guardrail evaluators."""

    variables: dict[str, Any] = field(default_factory=dict)

    def update_from_tool_output(self, tool_name: str, output: dict[str, Any]) -> None:
        # Promote scalar outputs to top-level keys so guardrail expressions
        # can reference them directly (e.g. `refund_amount > 500`).
        for k, v in output.items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                # Map well-known keys (`amount_usd` from propose_refund)
                if tool_name == "propose_refund" and k == "amount_usd":
                    self.variables["refund_amount"] = v
                self.variables[f"{tool_name}.{k}"] = v


@dataclass
class AOPExecutor:
    llm: LLMClient
    registry: Any  # tools.Registry; typed as Any to avoid heavy import in tests

    max_steps: int = 12

    async def run(
        self,
        *,
        aop: AOP,
        case_context: dict[str, Any],
        tool_context: Any,  # tools.ToolContext
        granted_scopes: list[str],
        aop_version_id: str,
        case_id: str,
        trace_id: str | None = None,
    ) -> AOPRunOutcome:
        trace_id = trace_id or str(uuid4())
        started_at = datetime.now(UTC)
        run_id = str(uuid4())

        scope_set = set(granted_scopes)
        allowed_tool_names = [
            name
            for name, t in self.registry.tools.items()
            if set(t.required_scopes).issubset(scope_set)
        ]
        tool_specs = self.registry.to_openai_specs(only=allowed_tool_names)

        system_prompt = self._build_system_prompt(aop, granted_scopes)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(case_context, default=str)},
        ]

        steps: list[AOPStepResult] = []
        usage = TokenUsage()
        state = ExecutorRuntimeState(variables={"case_id": case_id})
        status: str = "failed"
        outcome_reason: str | None = None

        for _ in range(self.max_steps):
            resp = await self.llm.complete(messages, tools=tool_specs)
            usage.add(resp.usage)

            if not resp.tool_calls:
                # Treat as terminal: model has emitted the final response.
                steps.append(
                    AOPStepResult(
                        step_index=len(steps),
                        tool_name="(final_message)",
                        input={"text": resp.text},
                        output={"text": resp.text},
                        status="succeeded",
                        cost_usd=resp.usage.cost_usd,
                    )
                )
                status = "resolved"
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": resp.text or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in resp.tool_calls
                    ],
                }
            )

            for call in resp.tool_calls:
                t0 = time.perf_counter()
                step_status = "succeeded"
                error: str | None = None
                output_dict: dict[str, Any] = {}

                try:
                    tool = self.registry.get(call.name)
                    if not set(tool.required_scopes).issubset(scope_set):
                        raise PermissionError(
                            f"tool '{call.name}' missing scopes "
                            f"{sorted(set(tool.required_scopes) - scope_set)}"
                        )
                    parsed = tool.input_schema.model_validate(call.arguments)
                    result = await tool.func(tool_context, parsed)
                    output_dict = result.model_dump()
                except Exception as e:
                    step_status = "failed"
                    error = str(e)
                    output_dict = {"error": error}

                latency_ms = int((time.perf_counter() - t0) * 1000)
                steps.append(
                    AOPStepResult(
                        step_index=len(steps),
                        tool_name=call.name,
                        input=call.arguments,
                        output=output_dict,
                        status=step_status,
                        latency_ms=latency_ms,
                        cost_usd=0.0,  # tool itself has no LLM cost
                        error=error,
                    )
                )
                state.update_from_tool_output(call.name, output_dict)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(output_dict, default=str),
                    }
                )

                # Evaluate guardrails after each tool result. A halting
                # guardrail short-circuits; an approval-required guardrail
                # routes to inbox.
                violations = evaluate_guardrails(aop.guardrails, state.variables)
                halt_reason = self._reduce_violations(violations)
                if halt_reason is not None:
                    halt_status, halt_message = halt_reason
                    steps.append(
                        AOPStepResult(
                            step_index=len(steps),
                            tool_name="(guardrail)",
                            input={},
                            output={"violation": halt_message},
                            status="halted_by_guardrail",
                            error=halt_message,
                        )
                    )
                    status = halt_status
                    outcome_reason = halt_message
                    return AOPRunOutcome(
                        run_id=run_id,
                        aop_version_id=aop_version_id,
                        case_id=case_id,
                        status=status,
                        started_at=started_at,
                        ended_at=datetime.now(UTC),
                        steps=steps,
                        cost_usd=usage.cost_usd,
                        token_in=usage.prompt_tokens,
                        token_out=usage.completion_tokens,
                        trace_id=trace_id,
                    )
        else:
            status = "failed"
            outcome_reason = f"exceeded max_steps={self.max_steps}"

        if outcome_reason:
            steps.append(
                AOPStepResult(
                    step_index=len(steps),
                    tool_name="(executor)",
                    input={},
                    output={"reason": outcome_reason},
                    status="failed",
                    error=outcome_reason,
                )
            )

        return AOPRunOutcome(
            run_id=run_id,
            aop_version_id=aop_version_id,
            case_id=case_id,
            status=status,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            steps=steps,
            cost_usd=usage.cost_usd,
            token_in=usage.prompt_tokens,
            token_out=usage.completion_tokens,
            trace_id=trace_id,
        )

    @staticmethod
    def _reduce_violations(
        violations: list[GuardrailViolation],
    ) -> tuple[str, str] | None:
        """Map guardrail violations to (run_status, message) or None to continue."""
        for v in violations:
            if v.kind == "halt_on":
                return ("failed", f"halt_on: {v.message}")
            if v.kind == "requires_approval_if":
                return ("escalated_human", f"requires_approval_if: {v.message}")
        return None

    @staticmethod
    def _build_system_prompt(aop: AOP, granted_scopes: list[str]) -> str:
        scopes = ", ".join(granted_scopes) or "(none)"
        steps_outline = "\n".join(
            f"  {i+1}. {s.name} (tool={s.tool})" for i, s in enumerate(aop.steps)
        )
        guardrails_text = "\n".join(
            f"  - {g.kind}: {g.expr}" + (f" ({g.message})" if g.message else "")
            for g in aop.guardrails
        ) or "  (none)"
        return (
            f"You are executing the Cogency AOP '{aop.name}'.\n"
            f"{aop.description}\n\n"
            f"Granted scopes: {scopes}\n\n"
            f"Step outline (for reference, not strict ordering):\n{steps_outline}\n\n"
            f"Hard guardrails (enforced by the runtime; do not attempt to bypass):\n"
            f"{guardrails_text}\n\n"
            f"Procedure:\n{aop.body}\n\n"
            "Operating rules:\n"
            "- Use tools to read state and to write changes back to Salesforce.\n"
            "- After completing the procedure, emit a short final message summarizing the outcome.\n"
            "- If you cannot complete the procedure, emit a final message explaining why.\n"
            "- Never invent customer data; ground every factual claim in tool results.\n"
        )
