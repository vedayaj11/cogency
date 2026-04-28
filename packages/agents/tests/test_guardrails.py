"""Guardrail expression evaluator unit tests."""

from __future__ import annotations

from agents.guardrails import evaluate_guardrails
from aop import Guardrail


def test_numeric_comparison_fires():
    g = [Guardrail(kind="requires_approval_if", expr="refund_amount > 500")]
    violations = evaluate_guardrails(g, {"refund_amount": 750})
    assert len(violations) == 1
    assert violations[0].kind == "requires_approval_if"


def test_numeric_comparison_below_threshold_passes():
    g = [Guardrail(kind="requires_approval_if", expr="refund_amount > 500")]
    assert evaluate_guardrails(g, {"refund_amount": 100}) == []


def test_boolean_equals():
    g = [Guardrail(kind="halt_on", expr="identity_verified == false")]
    assert len(evaluate_guardrails(g, {"identity_verified": False})) == 1
    assert evaluate_guardrails(g, {"identity_verified": True}) == []


def test_string_equals_with_quotes():
    g = [Guardrail(kind="halt_on", expr='customer_tier == "blocked"')]
    assert len(evaluate_guardrails(g, {"customer_tier": "blocked"})) == 1
    assert evaluate_guardrails(g, {"customer_tier": "enterprise"}) == []


def test_missing_variable_does_not_fire():
    g = [Guardrail(kind="halt_on", expr="never_set > 0")]
    assert evaluate_guardrails(g, {"other": 1}) == []


def test_max_cost_caps():
    g = [Guardrail(kind="max_cost_usd", expr="0.50")]
    assert evaluate_guardrails(g, {"cost_usd": 0.75})
    assert evaluate_guardrails(g, {"cost_usd": 0.10}) == []


def test_unrecognized_expression_passes_silently():
    g = [Guardrail(kind="halt_on", expr="x and y")]
    assert evaluate_guardrails(g, {"x": True, "y": True}) == []
