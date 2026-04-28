"""AOP DSL types.

An AOP source file is markdown with a YAML frontmatter outline. Frontmatter
declares structured steps (tools, scopes, IO shapes, fallbacks); markdown body
is the natural-language procedure. Compiler validates the outline; runtime
hands the markdown body to the LLM as instructions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Guardrail(BaseModel):
    """Hard guardrail — declarable, enforced at runtime, violations route to inbox."""

    kind: Literal["requires_approval_if", "halt_on", "max_cost_usd"]
    expr: str
    message: str | None = None


class Step(BaseModel):
    name: str
    tool: str
    required_scopes: list[str] = Field(default_factory=list)
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    fallback: str | None = None
    timeout_seconds: int = 60
    retries: int = 3


class AOP(BaseModel):
    name: str
    description: str
    persona_id: str | None = None
    steps: list[Step]
    guardrails: list[Guardrail] = Field(default_factory=list)
    body: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
