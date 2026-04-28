"""Compile an AOP into an executable plan.

PRD AC2.2 — validate: tool existence, permission scope coverage, IO shape
integrity, cycles. Errors surface inline with line references.
"""

from __future__ import annotations

from collections.abc import Iterable

from aop.dsl import AOP


class CompileError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def compile_aop(
    aop: AOP,
    *,
    available_tools: Iterable[str],
    granted_scopes: Iterable[str],
) -> AOP:
    """Validate the AOP against the tool registry and scope grant.

    Returns the AOP unchanged on success; raises CompileError otherwise.
    """
    errors: list[str] = []
    tool_set = set(available_tools)
    scope_set = set(granted_scopes)

    seen_names: set[str] = set()
    for step in aop.steps:
        if step.name in seen_names:
            errors.append(f"duplicate step name: {step.name}")
        seen_names.add(step.name)

        if step.tool not in tool_set:
            errors.append(f"step '{step.name}' references unknown tool '{step.tool}'")

        missing_scopes = set(step.required_scopes) - scope_set
        if missing_scopes:
            errors.append(
                f"step '{step.name}' missing scopes: {sorted(missing_scopes)}"
            )

    if errors:
        raise CompileError(errors)
    return aop
