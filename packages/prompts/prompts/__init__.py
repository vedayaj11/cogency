"""Versioned prompt artifacts.

PRD §8.3: every prompt is a Langfuse prompt artifact (versioned, variabled).
Code references prompts by name + version; deploys never inline prompts.
"""

from prompts.registry import PROMPTS, Prompt

__all__ = ["PROMPTS", "Prompt"]
