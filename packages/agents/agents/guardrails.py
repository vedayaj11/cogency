"""Guardrail expression evaluator.

PRD AC2.4: hard guardrails declarable on an AOP, e.g.
`requires_approval_if(refund_amount > 500)` or `halt_on(identity_verify_failed)`.

For MVP we support a deliberately narrow expression grammar: a single binary
comparison between an identifier (resolved against the executor's runtime
variables) and a literal (number, string, bool). This avoids dragging in a
full sandboxed expression engine while covering ~all of the guardrail patterns
shown in the PRD examples.

Supported forms:
    refund_amount > 500
    refund_amount >= 500
    identity_verified == false
    customer_tier != "enterprise"
"""

from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from typing import Any

from aop import Guardrail


_OPS = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
}

_PATTERN = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*(>=|<=|==|!=|>|<)\s*(.+?)\s*$"
)


@dataclass
class GuardrailViolation:
    kind: str
    expr: str
    message: str


def _coerce_literal(raw: str) -> Any:
    raw = raw.strip()
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.lower() in {"null", "none"}:
        return None
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw  # bare identifier-as-string fallback


def evaluate_guardrails(
    guardrails: list[Guardrail], variables: dict[str, Any]
) -> list[GuardrailViolation]:
    """Return guardrails whose expression evaluates True for the given vars."""
    violations: list[GuardrailViolation] = []
    for g in guardrails:
        if g.kind == "max_cost_usd":
            # Special-cased: compare against a synthetic "cost_usd" var if present.
            cap = float(g.expr)
            if variables.get("cost_usd", 0) > cap:
                violations.append(
                    GuardrailViolation(
                        kind=g.kind,
                        expr=g.expr,
                        message=g.message or f"cost exceeded {cap}",
                    )
                )
            continue

        if not _evaluate_comparison(g.expr, variables):
            continue
        violations.append(
            GuardrailViolation(
                kind=g.kind,
                expr=g.expr,
                message=g.message or g.expr,
            )
        )
    return violations


def _evaluate_comparison(expr: str, variables: dict[str, Any]) -> bool:
    m = _PATTERN.match(expr)
    if not m:
        return False
    ident, op_sym, rhs = m.group(1), m.group(2), m.group(3)
    if ident not in variables:
        return False
    lhs_value = variables[ident]
    rhs_value = _coerce_literal(rhs)
    op = _OPS.get(op_sym)
    if op is None:
        return False
    try:
        return bool(op(lhs_value, rhs_value))
    except TypeError:
        return False
