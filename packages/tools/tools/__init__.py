"""Tool registry.

Each tool declares: name, required scopes, Pydantic input/output schema, and
an async callable. Tools are wrapped as Temporal Activities at the worker
edge so they get retry/idempotency/timeout for free.
"""

from tools.registry import REGISTRY, Tool, register

__all__ = ["REGISTRY", "Tool", "register"]
