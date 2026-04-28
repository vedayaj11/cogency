"""Tool registry + built-in tool catalog.

Tools are wrapped as Temporal Activities at the worker edge so they get
retry/idempotency/timeout for free (PRD §8.3). For MVP, tool dispatch happens
inline within the AOP executor activity; promoting individual tools to their
own activities is a follow-up.
"""

from tools.builtin import build_default_registry
from tools.registry import REGISTRY, Registry, Tool, ToolContext, register

__all__ = [
    "REGISTRY",
    "Registry",
    "Tool",
    "ToolContext",
    "register",
    "build_default_registry",
]
