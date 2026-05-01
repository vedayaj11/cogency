"""ORM models for cogency.knowledge_sources + cogency.knowledge_chunks.

Distinct from sf.knowledge_article_version (which mirrors Salesforce KAV).
The `embedding` column is left as `Any`-typed because at runtime it may be
either pgvector's `vector(1536)` (production) or `double precision[]`
(local dev without pgvector). Both are read/written via plain Python lists
of floats; cosine similarity is computed in Python on read.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "uri", name="uq_knowledge_sources_tenant_uri"),
        {"schema": "cogency"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)  # markdown|pdf|url|sf_kav
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    last_indexed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_knowledge_chunks_source_index"),
        {"schema": "cogency"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cogency.knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Stored as float[] when pgvector is unavailable, vector(1536) otherwise.
    # SQLAlchemy reads both as a list-like; we coerce to list[float] in code.
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), default=None)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
