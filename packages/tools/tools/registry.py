from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    name: str
    required_scopes: list[str]
    input_schema: type
    output_schema: type
    func: Callable[..., Awaitable[Any]]
    description: str = ""


@dataclass
class _Registry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"tool '{tool.name}' already registered")
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self.tools[name]

    def names(self) -> list[str]:
        return sorted(self.tools)


REGISTRY = _Registry()


def register(tool: Tool) -> Tool:
    REGISTRY.register(tool)
    return tool
