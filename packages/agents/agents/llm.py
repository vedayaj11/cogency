"""OpenAI chat-completions wrapper with tool-calling support and cost accounting.

PRD §8.1 specifies Claude Sonnet 4.5; this build uses OpenAI per project
decision. The interface is provider-agnostic so swapping is a matter of
substituting `LLMClient` impl, not changing call sites.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI


# gpt-4o pricing as of late-2024 / early-2026, USD per 1M tokens.
# Update when OpenAI changes pricing; per-tenant cost rollups depend on this.
_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
}


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, other: TokenUsage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cost_usd += other.cost_usd


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    usage: TokenUsage
    finish_reason: str | None = None


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate = _PRICING_PER_1M.get(model)
    if rate is None:
        return 0.0
    in_rate, out_rate = rate
    return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000


@dataclass
class LLMClient:
    api_key: str
    model: str = "gpt-4o"
    _client: AsyncOpenAI | None = field(default=None, init=False, repr=False)

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        resp = await self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        text = choice.message.content or ""

        calls: list[ToolCall] = []
        for tc in choice.message.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        usage = TokenUsage(
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
            total_tokens=resp.usage.total_tokens if resp.usage else 0,
        )
        usage.cost_usd = estimate_cost(
            self.model, usage.prompt_tokens, usage.completion_tokens
        )

        return LLMResponse(
            text=text,
            tool_calls=calls,
            usage=usage,
            finish_reason=choice.finish_reason,
        )
