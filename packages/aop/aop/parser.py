"""Parse an AOP source markdown file into an AOP model.

Format:

    ---
    name: refund_under_500
    description: Refund a single order under $500.
    persona_id: support_brand_voice_v3
    steps:
      - name: verify_identity
        tool: verify_customer_identity
        required_scopes: [contact.read]
        inputs:
          contact_id: case.contact_id
      - ...
    guardrails:
      - kind: requires_approval_if
        expr: refund_amount > 500
    ---

    Body markdown — the natural-language procedure handed to the LLM.
"""

from __future__ import annotations

import yaml

from aop.dsl import AOP


def parse_aop_source(source: str) -> AOP:
    """Split frontmatter + body, validate against the AOP model."""
    if not source.startswith("---"):
        raise ValueError("AOP source must begin with '---' frontmatter delimiter")
    parts = source.split("---", 2)
    if len(parts) < 3:
        raise ValueError("AOP source missing closing '---' delimiter")
    _, frontmatter, body = parts

    data = yaml.safe_load(frontmatter) or {}
    data["body"] = body.strip()
    return AOP.model_validate(data)
