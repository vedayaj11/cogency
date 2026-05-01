"""Async OpenAI embeddings wrapper.

Adapted from llm-chatbot's `OpenAIEmbeddingModel` (rag_app.py:160–205).
Changes:
- `AsyncOpenAI` instead of the sync client (cogency is fully async).
- Default model is `text-embedding-3-large` matching cogency's
  `Settings.openai_embedding_model`.
- Batch size honored (OpenAI accepts up to 2048; we use 100 to keep retries
  cheap on transient failures).
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from openai import AsyncOpenAI


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in pure Python — used as the portable cosine path
    when pgvector isn't installed. Returns 0.0 for empty / mismatched
    vectors rather than raising.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class OpenAIEmbeddings:
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large",
        *,
        batch_size: int = 100,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY required")
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.batch_size = batch_size

    async def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        """Embed many texts in batches. Order-preserving."""
        text_list = list(texts)
        if not text_list:
            return []
        out: list[list[float]] = []
        for i in range(0, len(text_list), self.batch_size):
            batch = text_list[i : i + self.batch_size]
            resp = await self._client.embeddings.create(input=batch, model=self.model)
            out.extend([item.embedding for item in resp.data])
        return out

    async def embed_query(self, query: str) -> list[float]:
        resp = await self._client.embeddings.create(input=[query], model=self.model)
        return resp.data[0].embedding
