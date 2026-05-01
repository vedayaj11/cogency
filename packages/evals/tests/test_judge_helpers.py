"""Pure-logic tests for the judge module — prompt construction + parsing.

The actual LLM call is exercised end-to-end by the smoke test; here we
just verify the deterministic plumbing.
"""

from __future__ import annotations

from evals.judge import (
    DEFAULT_RUBRIC,
    _estimate_cost,
    _parse_scores_json,
    _summarize_steps,
)


def test_default_rubric_has_four_dimensions():
    assert set(DEFAULT_RUBRIC.keys()) == {
        "task_completion",
        "policy_adherence",
        "tone",
        "citation_accuracy",
    }


def test_summarize_steps_marks_status():
    steps = [
        {"step_index": 0, "tool_name": "lookup_case", "status": "succeeded", "output": {"found": True}},
        {"step_index": 1, "tool_name": "(guardrail)", "status": "halted_by_guardrail", "output": {}, "error": "x > 500"},
        {"step_index": 2, "tool_name": "send_email_reply", "status": "failed", "output": {"error": "no client"}, "error": "no client"},
    ]
    out = _summarize_steps(steps)
    assert "✓" in out  # succeeded
    assert "!" in out  # halted
    assert "✗" in out  # failed


def test_summarize_steps_truncates_after_30():
    steps = [{"step_index": i, "tool_name": "x", "status": "succeeded", "output": {}} for i in range(50)]
    out = _summarize_steps(steps)
    assert "more steps truncated" in out


def test_parse_scores_json_strips_markdown_fences():
    text = '```json\n{"task_completion": 0.9, "tone": 0.8}\n```'
    parsed = _parse_scores_json(text)
    assert parsed["task_completion"] == 0.9


def test_parse_scores_json_returns_empty_on_garbage():
    assert _parse_scores_json("not json at all") == {}


def test_estimate_cost_known_models():
    # gpt-4o: $2.50/1M in + $10.00/1M out → 0.0001 + 0.0001 ≈ 0.000125 + 0.0005 = 0.000625
    assert _estimate_cost("gpt-4o", 100, 50) > 0
    assert _estimate_cost("claude-sonnet-4-5", 100, 50) > 0


def test_estimate_cost_unknown_model_returns_zero():
    assert _estimate_cost("claude-haiku-99", 100, 50) == 0.0
