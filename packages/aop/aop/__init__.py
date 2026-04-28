"""AOP Engine — the spine.

PRD §6.2: NL+structured outline → compiled plan → Temporal-wrapped execution
with guardrails, versioning, dry-run, full trace capture.
"""

from aop.compiler import CompileError, compile_aop
from aop.dsl import AOP, Guardrail, Step
from aop.parser import parse_aop_source

__all__ = ["AOP", "Step", "Guardrail", "compile_aop", "CompileError", "parse_aop_source"]
