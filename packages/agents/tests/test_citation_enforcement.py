"""Citation-enforcement guardrail tests.

The check fires only when:
1. The AOP sets `metadata.require_citations: true`
2. lookup_knowledge was actually called and succeeded in the run
3. The final message contains uncited factual segments

If any of those is false, the run resolves normally.
"""

from __future__ import annotations

from agents.citation_check import enforce_citations


def test_uncited_factual_claim_triggers():
    text = "Refunds over 500 dollars require approval. The cycle is 30 days."
    v = enforce_citations(text)
    assert v is not None
    assert v.segments  # at least one uncited segment


def test_cited_factual_claim_passes():
    text = (
        "Refunds over 500 dollars require approval [cite:abc123]. "
        "The cycle is 30 days [cite:def456]."
    )
    assert enforce_citations(text) is None


def test_no_factual_claims_passes():
    text = "Hi, thanks for reaching out. I will look into your case."
    assert enforce_citations(text) is None


def test_partial_citation_still_triggers():
    """If one factual sentence is cited but another isn't, fire."""
    text = (
        "Refunds over 500 dollars require approval [cite:abc123]. "
        "The 30-day window is firm."
    )
    v = enforce_citations(text)
    assert v is not None
