"""Token-aware paragraph-first chunker.

Adapted from llm-chatbot's `SimpleTextDocumentParser.parse_and_chunk`
(rag_app.py:740–840). Changes from the original:

1. Returns `Chunk` objects (with `chunk_index` + `metadata`) instead of
   bare strings, so citation context survives all the way to retrieval.
2. `metadata` from the caller is propagated to every emitted chunk
   (e.g. `source_uri`, `page_num`).
3. Pure synchronous (no I/O), so no async-conversion needed — we wrap
   it in async drivers downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import tiktoken

from rag.types import Chunk


@dataclass
class TokenChunker:
    chunk_size: int = 1000
    overlap_size: int = 200
    encoding_name: str = "cl100k_base"

    def __post_init__(self) -> None:
        self._encoding = tiktoken.get_encoding(self.encoding_name)

    def count_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def split(self, content: str, *, base_metadata: dict[str, Any] | None = None) -> list[Chunk]:
        """Split `content` into Chunks with token-aware overlap.

        - Paragraph-first: chunks try to align on `\\n\\n` boundaries.
        - Sentences as fallback when a paragraph itself is over the budget.
        - Overlap text is taken from the trailing words of the previous chunk
          up to `overlap_size` tokens.
        """
        content = content.strip()
        if not content:
            return []

        base_meta = dict(base_metadata or {})

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        chunks_text: list[str] = []
        current_chunk = ""
        current_tokens = 0

        for paragraph in paragraphs:
            paragraph_tokens = self.count_tokens(paragraph)

            # Single paragraph too big — split by sentences.
            if paragraph_tokens > self.chunk_size:
                if current_chunk:
                    chunks_text.append(current_chunk.strip())
                    current_chunk = ""
                    current_tokens = 0

                sentences = self._split_by_sentences(paragraph)
                temp_chunk = ""
                temp_tokens = 0
                for sentence in sentences:
                    sentence_tokens = self.count_tokens(sentence)
                    if temp_tokens + sentence_tokens > self.chunk_size and temp_chunk:
                        chunks_text.append(temp_chunk.strip())
                        overlap_text = self._get_overlap_text(temp_chunk, self.overlap_size)
                        temp_chunk = (overlap_text + " " + sentence) if overlap_text else sentence
                        temp_tokens = self.count_tokens(temp_chunk)
                    else:
                        temp_chunk = (temp_chunk + " " + sentence) if temp_chunk else sentence
                        temp_tokens += sentence_tokens
                if temp_chunk:
                    current_chunk = temp_chunk
                    current_tokens = temp_tokens

            # Normal: try to add paragraph to current chunk.
            elif current_tokens + paragraph_tokens > self.chunk_size and current_chunk:
                chunks_text.append(current_chunk.strip())
                overlap_text = self._get_overlap_text(current_chunk, self.overlap_size)
                current_chunk = (overlap_text + "\n\n" + paragraph) if overlap_text else paragraph
                current_tokens = self.count_tokens(current_chunk)
            else:
                current_chunk = (current_chunk + "\n\n" + paragraph) if current_chunk else paragraph
                current_tokens += paragraph_tokens

        if current_chunk:
            chunks_text.append(current_chunk.strip())

        return [
            Chunk(text=t, chunk_index=i, metadata=dict(base_meta))
            for i, t in enumerate(chunks_text)
        ]

    @staticmethod
    def _split_by_sentences(text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _get_overlap_text(self, text: str, max_tokens: int) -> str:
        """Trailing-word overlap up to `max_tokens` tokens."""
        words = text.split()
        overlap_words: list[str] = []
        token_count = 0
        for word in reversed(words):
            wt = self.count_tokens(word)
            if token_count + wt > max_tokens:
                break
            overlap_words.insert(0, word)
            token_count += wt
        return " ".join(overlap_words)
