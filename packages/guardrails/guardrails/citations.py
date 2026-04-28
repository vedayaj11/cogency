"""Citation-required factual mode.

PRD AC7.3: any AI factual claim without a citation_id is suppressed and logged.
Hallucination rate target: <2% on a 1000-claim red-team test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


CITATION_PATTERN = re.compile(r"\[cite:([a-zA-Z0-9_-]+)\]")


@dataclass(frozen=True)
class CitationCheck:
    has_claims: bool
    cited_chunk_ids: tuple[str, ...]
    uncited_segments: tuple[str, ...]


def extract_citations(text: str) -> CitationCheck:
    """Extract chunk-id citations and flag uncited factual segments.

    Heuristic for MVP: a "factual segment" is a sentence containing a number,
    proper noun, or known policy keyword. Real implementation should classify
    factuality via a small model or regex policy lexicon.
    """
    cited = tuple(m.group(1) for m in CITATION_PATTERN.finditer(text))
    sentences = re.split(r"(?<=[.!?])\s+", text)
    uncited = tuple(
        s
        for s in sentences
        if _looks_factual(s) and not CITATION_PATTERN.search(s)
    )
    return CitationCheck(
        has_claims=any(_looks_factual(s) for s in sentences),
        cited_chunk_ids=cited,
        uncited_segments=uncited,
    )


def _looks_factual(sentence: str) -> bool:
    return bool(re.search(r"\d", sentence)) or bool(
        re.search(r"\b(refund|policy|warranty|charge|fee|SLA|hours)\b", sentence, re.I)
    )
