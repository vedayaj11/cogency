"""Eval & Observability.

PRD §6.6: golden datasets, LLM-as-judge rubrics, side-by-side trace diffs,
deployment gate (block deploy if pass rate <85%).
"""

from evals.judge import DEFAULT_RUBRIC, JudgeScore, judge_run
from evals.rubric import Rubric, RubricScore

__all__ = ["Rubric", "RubricScore", "judge_run", "JudgeScore", "DEFAULT_RUBRIC"]
