"""Shared types for the RAG package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class Chunk:
    """A chunk produced by the chunker, before embedding/storage.

    `metadata` carries citation context (source_uri, page_num, span_*) that
    survives all the way to retrieval — without it we can't do
    citation-grounded answering per PRD AC7.3.
    """

    text: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """A chunk returned from the vector store with similarity score."""

    chunk_id: UUID
    source_id: UUID
    text: str
    score: float
    metadata: dict[str, Any]
    chunk_index: int

    @property
    def citation_id(self) -> str:
        """Stable string id for citation references like `[cite:abc123]`."""
        return self.chunk_id.hex[:12]
