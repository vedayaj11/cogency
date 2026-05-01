"""PgVectorStore — cogency.knowledge_chunks read/write.

Storage format:
- When pgvector is installed, the `embedding` column is `vector(1536)` and
  similarity could be computed with the `<=>` operator + an HNSW index. We
  add an HNSW index in migration 0004 when pgvector is present.
- When pgvector is unavailable (local Postgres 14 without the extension),
  the column is `double precision[]`. SQLAlchemy reads/writes both as a
  Python list[float].

Cosine similarity is currently computed in Python on retrieval for
portability. When the production deployment lands on Postgres 16+pgvector,
we'll add a `query_similar_native()` path that uses `embedding <=> :query`
for ANN — same API, faster on large corpora.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.knowledge import KnowledgeChunk, KnowledgeSource
from rag.embeddings import cosine_similarity
from rag.types import Chunk, RetrievedChunk


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


@dataclass
class PgVectorStore:
    session: AsyncSession

    # ---------- sources ----------

    async def upsert_source(
        self,
        *,
        tenant_id: UUID,
        type: str,
        uri: str,
        title: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeSource:
        existing = (
            await self.session.execute(
                select(KnowledgeSource).where(
                    KnowledgeSource.tenant_id == tenant_id,
                    KnowledgeSource.uri == uri,
                )
            )
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if existing:
            existing.type = type
            existing.title = title
            existing.metadata_ = metadata or {}
            existing.last_indexed_at = now
            await self.session.commit()
            return existing
        source = KnowledgeSource(
            tenant_id=tenant_id,
            type=type,
            uri=uri,
            title=title,
            metadata_=metadata or {},
            last_indexed_at=now,
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    # ---------- chunks ----------

    async def upsert_chunks(
        self,
        *,
        tenant_id: UUID,
        source_id: UUID,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) / embeddings ({len(embeddings)}) length mismatch"
            )
        if not chunks:
            return 0
        # `insert(...).values(...)` operates against the underlying Table —
        # so keys must be DB column names, not ORM attribute names. Our ORM
        # attribute is `metadata_` (Python rename to dodge SQLAlchemy's
        # reserved `metadata` on Base) but the DB column is `metadata`.
        rows = [
            {
                "tenant_id": tenant_id,
                "source_id": source_id,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "embedding": e,
                "metadata": c.metadata,
                "content_hash": _content_hash(c.text),
                "is_active": True,
            }
            for c, e in zip(chunks, embeddings, strict=True)
        ]
        # Use the underlying Table directly to bypass the ORM property/
        # attribute lookup that fails on `metadata` (a reserved attr).
        stmt = insert(KnowledgeChunk.__table__).values(rows)
        update_cols = {
            "text": stmt.excluded.text,
            "embedding": stmt.excluded.embedding,
            "metadata": stmt.excluded.metadata,
            "content_hash": stmt.excluded.content_hash,
            "is_active": stmt.excluded.is_active,
        }
        # ON CONFLICT (source_id, chunk_index) so re-ingestion is idempotent.
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_id", "chunk_index"],
            set_=update_cols,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def deactivate_source(self, *, source_id: UUID) -> int:
        from sqlalchemy import update

        result = await self.session.execute(
            update(KnowledgeChunk)
            .where(KnowledgeChunk.source_id == source_id)
            .values(is_active=False)
        )
        await self.session.commit()
        return result.rowcount or 0

    # ---------- retrieval ----------

    async def query_similar(
        self,
        *,
        tenant_id: UUID,
        query_embedding: list[float],
        top_k: int = 5,
        source_ids: list[UUID] | None = None,
        min_score: float = 0.0,
    ) -> list[RetrievedChunk]:
        """Return the top-k chunks ranked by cosine similarity.

        Python-side cosine — fine for tens of thousands of chunks per tenant.
        For larger corpora, swap in a pgvector ANN path (see module docstring).
        """
        stmt = select(KnowledgeChunk).where(
            KnowledgeChunk.tenant_id == tenant_id,
            KnowledgeChunk.is_active.is_(True),
            KnowledgeChunk.embedding.is_not(None),
        )
        if source_ids:
            stmt = stmt.where(KnowledgeChunk.source_id.in_(source_ids))

        candidates = list((await self.session.execute(stmt)).scalars().all())
        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk in candidates:
            emb = chunk.embedding
            if not emb:
                continue
            score = cosine_similarity(query_embedding, list(emb))
            if score >= min_score:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]
        return [
            RetrievedChunk(
                chunk_id=c.id,
                source_id=c.source_id,
                text=c.text,
                score=s,
                metadata=c.metadata_ or {},
                chunk_index=c.chunk_index,
            )
            for s, c in top
        ]
