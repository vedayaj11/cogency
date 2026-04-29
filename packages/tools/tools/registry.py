"""Tool registry primitives.

Each tool declares: name, description, required scopes, Pydantic input/output
schemas, and an async callable that takes a `ToolContext` plus the parsed
input model. The registry exposes both a Python lookup interface and an
OpenAI-compatible JSON schema for tool calling.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# SalesforceClient is only needed for tools that write back to SF; tools that
# read from the local mirror don't need it. Keep the import optional via
# string annotation to avoid a hard dep on import time.
TIn = TypeVar("TIn", bound=BaseModel)
TOut = TypeVar("TOut", bound=BaseModel)


@dataclass
class ToolContext:
    """Per-run context handed to every tool invocation."""

    tenant_id: UUID
    case_id: str | None = None
    session: AsyncSession | None = None
    sf_client: Any | None = None  # SalesforceClient; Any to avoid import cycle


@dataclass
class Tool(Generic[TIn, TOut]):
    name: str
    description: str
    required_scopes: list[str]
    input_schema: type[TIn]
    output_schema: type[TOut]
    func: Callable[[ToolContext, TIn], Awaitable[TOut]]
    # When True, the executor halts before invoking this tool, records an
    # `awaiting_approval` step, and creates an inbox item carrying the
    # proposed call arguments. A human approves from /inbox; the inbox-
    # approve endpoint re-fires the call via OutboxWriter. Default False —
    # write tools that should be auto-fired (internal notes, low-stakes
    # field updates) leave it False; high-stakes writes (external email,
    # close case, escalation) set it True.
    requires_approval: bool = False
    # Read tools are eligible for parallel dispatch when the LLM emits
    # multiple tool calls in one turn. Defaults to True for tools whose
    # required_scopes contain only `*.read`; computable but explicit is
    # safer.
    is_read_only: bool = False

    def to_openai_spec(self) -> dict[str, Any]:
        schema = self.input_schema.model_json_schema()
        # OpenAI rejects $ref-only schemas at the top level for some models;
        # prefer inlined definitions which Pydantic emits by default.
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


@dataclass
class Registry:
    tools: dict[str, Tool[Any, Any]] = field(default_factory=dict)

    def register(self, tool: Tool[Any, Any]) -> Tool[Any, Any]:
        if tool.name in self.tools:
            raise ValueError(f"tool '{tool.name}' already registered")
        self.tools[tool.name] = tool
        return tool

    def extend(self, tools: list[Tool[Any, Any]]) -> Registry:
        for t in tools:
            self.register(t)
        return self

    def get(self, name: str) -> Tool[Any, Any]:
        try:
            return self.tools[name]
        except KeyError as e:
            raise KeyError(f"tool '{name}' not registered") from e

    def names(self) -> list[str]:
        return sorted(self.tools)

    def to_openai_specs(self, only: list[str] | None = None) -> list[dict[str, Any]]:
        names = only or self.names()
        return [self.get(n).to_openai_spec() for n in names]


# Global default registry. Apps build this at startup and inject scoped copies
# into tool contexts. Tests typically construct a fresh Registry.
REGISTRY = Registry()


def register(tool: Tool[Any, Any]) -> Tool[Any, Any]:
    return REGISTRY.register(tool)
