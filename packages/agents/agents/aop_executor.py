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

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from aop import AOP, Guardrail
from schemas import AOPRunOutcome, AOPStepResult

from agents.guardrails import GuardrailViolation, evaluate_guardrails
from agents.llm import LLMClient, ToolCall, TokenUsage


class AOPExecutionError(Exception):
    pass


@dataclass
class ExecutorRuntimeState:
    """Mutable state visible to guardrail evaluators."""

    variables: dict[str, Any] = field(default_factory=dict)

    def update_from_tool_input(self, tool_name: str, input_args: dict[str, Any]) -> None:
        """Promote tool-call args into runtime state so guardrails can match
        on call arguments (e.g. `add_case_comment.is_public == true`)
        before the tool fires."""
        for k, v in input_args.items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                self.variables[f"{tool_name}.{k}"] = v

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

        # ---- M9a guardrails: PII redaction + prompt-injection scan + spotlight ----
        # Opt-in via AOP metadata so AOPs that need raw PII (e.g. legitimate
        # field updates that store the customer's email verbatim) can leave
        # redaction off. The activity that wraps the executor restores
        # redacted placeholders to their originals via the `restoration_map`
        # at write time.
        pii_redaction_on = bool(aop.metadata.get("pii_redaction"))
        injection_check_on = bool(aop.metadata.get("injection_check"))
        injection_action = str(aop.metadata.get("injection_action", "block"))
        injection_threshold = str(aop.metadata.get("injection_threshold", "high"))
        spotlight_on = bool(aop.metadata.get("spotlight_untrusted", True))

        # 1. Scan inbound case_context for prompt injection BEFORE any LLM call.
        if injection_check_on:
            from guardrails import scan_dict, severity_at_least

            injection = scan_dict(case_context)
            if injection.detected and severity_at_least(
                injection.max_severity, injection_threshold  # type: ignore[arg-type]
            ):
                if injection_action == "block":
                    return AOPRunOutcome(
                        run_id=run_id,
                        aop_version_id=aop_version_id,
                        case_id=case_id,
                        status="failed",
                        started_at=started_at,
                        ended_at=datetime.now(UTC),
                        steps=[
                            AOPStepResult(
                                step_index=0,
                                tool_name="(injection_scan)",
                                input={"scope": "case_context"},
                                output={
                                    "blocked": True,
                                    "summary": injection.summary,
                                    "hits": [
                                        {
                                            "name": h.pattern_name,
                                            "category": h.category,
                                            "severity": h.severity,
                                            "match": h.matched_text,
                                        }
                                        for h in injection.hits[:10]
                                    ],
                                },
                                status="halted_by_guardrail",
                                error=(
                                    f"prompt-injection blocked at "
                                    f"severity={injection.max_severity}: "
                                    f"{injection.summary}"
                                ),
                            )
                        ],
                        cost_usd=0.0,
                        token_in=0,
                        token_out=0,
                        trace_id=trace_id,
                    )
                # action == "warn": continue but record the hit as a step.

        # 2. Optionally redact PII in the case_context dict before it ever
        # hits an LLM message. Skip structural keys (case_id / status) since
        # those aren't PII and the agent needs them as bare values.
        restoration_map: dict[str, str] = {}
        if pii_redaction_on:
            from guardrails import get_redactor

            redactor = get_redactor()
            redacted_context, restoration_map = redactor.redact_dict(
                case_context,
                skip_keys={
                    "case_id",
                    "case_number",
                    "status",
                    "priority",
                    "origin",
                    "type",
                    "is_public",
                },
            )
            case_context = redacted_context

        scope_set = set(granted_scopes)
        allowed_tool_names = [
            name
            for name, t in self.registry.tools.items()
            if set(t.required_scopes).issubset(scope_set)
        ]
        tool_specs = self.registry.to_openai_specs(only=allowed_tool_names)

        system_prompt = self._build_system_prompt(
            aop, granted_scopes, spotlight_on=spotlight_on
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(case_context, default=str)},
        ]

        steps: list[AOPStepResult] = []
        # If injection_check is on with action=warn, surface a step recording
        # the early scan so the trace shows we noticed.
        if injection_check_on and injection_action == "warn":
            from guardrails import scan_dict as _sd

            early = _sd(case_context)
            if early.detected:
                steps.append(
                    AOPStepResult(
                        step_index=0,
                        tool_name="(injection_scan)",
                        input={"scope": "case_context"},
                        output={
                            "blocked": False,
                            "summary": early.summary,
                            "hit_count": len(early.hits),
                        },
                        status="succeeded",
                    )
                )
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

                # Citation enforcement (PRD AC7.3) — opt in via AOP metadata.
                # Fires only if the AOP set `metadata.require_citations: true`
                # AND the run actually retrieved knowledge during execution.
                # Otherwise honest "I don't know" answers and tool-only
                # responses (e.g. summaries) wouldn't be penalized.
                require_citations = bool(aop.metadata.get("require_citations"))
                used_knowledge = any(
                    s.tool_name == "lookup_knowledge" and s.status == "succeeded"
                    for s in steps
                )
                if require_citations and used_knowledge and resp.text:
                    from agents.citation_check import enforce_citations

                    violation = enforce_citations(resp.text)
                    if violation is not None:
                        steps.append(
                            AOPStepResult(
                                step_index=len(steps),
                                tool_name="(citation_check)",
                                input={"final_text": resp.text},
                                output={"uncited_segments": violation.segments},
                                status="halted_by_guardrail",
                                error=violation.message,
                            )
                        )
                        status = "escalated_human"
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

            # ---- Pre-call gates ----
            # 1. Feed each call's arguments into runtime state so AOP
            #    guardrails can match on tool input parameters.
            # 2. Check Tool.requires_approval and any AOP guardrail that
            #    fires given the proposed call. A gated call halts the run
            #    with status=escalated_human; the activity reads the
            #    `awaiting_approval` step's input field to create an inbox
            #    item carrying the proposed tool + args.
            for call in resp.tool_calls:
                state.update_from_tool_input(call.name, call.arguments)

            gated_call: ToolCall | None = None
            gated_reason: str | None = None
            for call in resp.tool_calls:
                try:
                    tool = self.registry.get(call.name)
                except KeyError:
                    continue  # let the dispatch loop record the failure
                if getattr(tool, "requires_approval", False):
                    gated_call, gated_reason = (
                        call,
                        f"tool '{call.name}' requires human approval",
                    )
                    break
                # Also evaluate AOP guardrails using the current state
                # (which now includes inputs for this call).
                violations = evaluate_guardrails(aop.guardrails, state.variables)
                pre_halt = self._reduce_violations(violations)
                if pre_halt is not None and pre_halt[0] == "escalated_human":
                    gated_call, gated_reason = call, pre_halt[1]
                    break

            if gated_call is not None:
                steps.append(
                    AOPStepResult(
                        step_index=len(steps),
                        tool_name=gated_call.name,
                        input=gated_call.arguments,
                        output={"awaiting_approval": True, "reason": gated_reason},
                        status="halted_by_guardrail",
                        error=gated_reason,
                    )
                )
                return AOPRunOutcome(
                    run_id=run_id,
                    aop_version_id=aop_version_id,
                    case_id=case_id,
                    status="escalated_human",
                    started_at=started_at,
                    ended_at=datetime.now(UTC),
                    steps=steps,
                    cost_usd=usage.cost_usd,
                    token_in=usage.prompt_tokens,
                    token_out=usage.completion_tokens,
                    trace_id=trace_id,
                )

            # ---- Dispatch ----
            # Calls run sequentially against the shared ToolContext session.
            # Parallel read dispatch is a future optimization that requires
            # per-call DB sessions (the SQLAlchemy AsyncSession can't be
            # shared between concurrent coroutines). The read/write
            # partition is preserved as documentation but currently both
            # run sequentially.
            async def _dispatch_one(call: ToolCall) -> tuple[
                ToolCall, str, dict[str, Any], str | None, int
            ]:
                t0 = time.perf_counter()
                try:
                    tool = self.registry.get(call.name)
                    if not set(tool.required_scopes).issubset(scope_set):
                        raise PermissionError(
                            f"tool '{call.name}' missing scopes "
                            f"{sorted(set(tool.required_scopes) - scope_set)}"
                        )
                    # PII tokenize-and-restore (PRD AC7.1): the LLM sees
                    # `<EMAIL_ADDRESS_0>` in its context, but tools must
                    # receive the originals to verify identity, send
                    # legitimate emails, etc. Auto-restore the call's
                    # arguments at the dispatch boundary using the map we
                    # built when redacting the case_context.
                    args = call.arguments
                    if pii_redaction_on and restoration_map:
                        from guardrails import restore as _restore_pii

                        def _walk_args(v: Any) -> Any:
                            if isinstance(v, str):
                                return _restore_pii(v, restoration_map)
                            if isinstance(v, dict):
                                return {k: _walk_args(x) for k, x in v.items()}
                            if isinstance(v, list):
                                return [_walk_args(x) for x in v]
                            return v

                        args = _walk_args(args)
                    parsed = tool.input_schema.model_validate(args)
                    result = await tool.func(tool_context, parsed)
                    return (call, "succeeded", result.model_dump(), None,
                            int((time.perf_counter() - t0) * 1000))
                except Exception as e:
                    return (call, "failed", {"error": str(e)}, str(e),
                            int((time.perf_counter() - t0) * 1000))

            dispatched: list[tuple[ToolCall, str, dict[str, Any], str | None, int]] = []
            for c in resp.tool_calls:
                dispatched.append(await _dispatch_one(c))

            for call, step_status, output_dict, error, latency_ms in dispatched:
                steps.append(
                    AOPStepResult(
                        step_index=len(steps),
                        tool_name=call.name,
                        input=call.arguments,
                        output=output_dict,
                        status=step_status,
                        latency_ms=latency_ms,
                        cost_usd=0.0,
                        error=error,
                    )
                )
                state.update_from_tool_output(call.name, output_dict)

                # Spotlight untrusted tool outputs before they enter the
                # LLM context. lookup_knowledge returns chunk text from
                # external documents — wrap so the model treats those
                # chunks as data, not instructions. Tools can opt out by
                # listing their name in the AOP's `metadata.trusted_tools`.
                content_for_llm: Any = output_dict
                trusted = set(aop.metadata.get("trusted_tools", []) or [])
                if (
                    spotlight_on
                    and call.name == "lookup_knowledge"
                    and call.name not in trusted
                ):
                    from guardrails import wrap_field

                    content_for_llm = wrap_field(output_dict)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(content_for_llm, default=str),
                    }
                )

            # ---- Post-result guardrails ----
            # Evaluate after each batch using accumulated outputs. A halting
            # guardrail short-circuits; a requires_approval guardrail that
            # fires here (rather than pre-call, e.g. amount-based) also
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
                return AOPRunOutcome(
                    run_id=run_id,
                    aop_version_id=aop_version_id,
                    case_id=case_id,
                    status=halt_status,
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
    def _build_system_prompt(
        aop: AOP, granted_scopes: list[str], *, spotlight_on: bool = True
    ) -> str:
        scopes = ", ".join(granted_scopes) or "(none)"
        steps_outline = "\n".join(
            f"  {i+1}. {s.name} (tool={s.tool})" for i, s in enumerate(aop.steps)
        )
        guardrails_text = "\n".join(
            f"  - {g.kind}: {g.expr}" + (f" ({g.message})" if g.message else "")
            for g in aop.guardrails
        ) or "  (none)"
        spotlight_block = ""
        if spotlight_on:
            from guardrails import SYSTEM_PROMPT_PREFIX

            spotlight_block = SYSTEM_PROMPT_PREFIX + "\n\n"
        return (
            f"{spotlight_block}"
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
