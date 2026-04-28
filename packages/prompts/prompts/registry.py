from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    body: str
    variables: tuple[str, ...] = ()


PROMPTS: dict[tuple[str, int], Prompt] = {}


def _add(prompt: Prompt) -> Prompt:
    PROMPTS[(prompt.name, prompt.version)] = prompt
    return prompt


META_AGENT_SELECTOR_V1 = _add(
    Prompt(
        name="meta_agent.selector",
        version=1,
        body=(
            "You are the Cogency meta-agent. Given a structured case context "
            "and a list of available AOPs, select the single best AOP to run "
            "or route to human. Emit JSON: "
            "{selected_aop_id, confidence, reasoning, fallback_aop_id, route_to_human}. "
            "Confidence must be in [0,1]; if no AOP exceeds the tenant threshold, "
            "set route_to_human=true and selected_aop_id=null."
        ),
        variables=("case_context", "aop_catalog", "tenant_threshold"),
    )
)


def get(name: str, version: int) -> Prompt:
    return PROMPTS[(name, version)]
