"""Final-message citation check.

Wraps `guardrails.guardrails.citations.extract_citations` (the
sentence-level factuality scanner) with an executor-friendly summary.

PRD AC7.3: any AI factual claim without a `citation_id` referencing an
indexed source is suppressed and logged. We don't suppress here — instead
the executor halts the run with `escalated_human` so a human can review
the proposed message before it's emitted to the customer. That preserves
the trace and the audit trail.

Activates only when the AOP opts in via `metadata.require_citations: true`
AND the run actually called `lookup_knowledge` (otherwise penalizing a
"I have no information on that" response is incorrect).
"""

from __future__ import annotations

from dataclasses import dataclass

from guardrails.citations import CITATION_PATTERN, extract_citations


@dataclass
class CitationViolation:
    segments: list[str]
    message: str


def enforce_citations(text: str) -> CitationViolation | None:
    """Return a CitationViolation if `text` contains uncited factual
    segments, else None.

    Uses the existing `extract_citations` helper from packages/guardrails
    which detects citation tokens of the form `[cite:abc123]` and flags
    sentences containing numbers / policy keywords without a citation.
    """
    check = extract_citations(text)
    if not check.uncited_segments:
        return None
    return CitationViolation(
        segments=list(check.uncited_segments[:5]),
        message=(
            f"final message has {len(check.uncited_segments)} uncited factual "
            "segment(s); require_citations is enabled and lookup_knowledge was "
            "available — every factual claim must end with [cite:<chunk_id>]"
        ),
    )


__all__ = ["enforce_citations", "CitationViolation"]
