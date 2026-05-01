"""Knowledge sources + chunks: cogency-native RAG storage.

Distinct from sf.knowledge_article_version (which mirrors Salesforce KAV).
Sources here include uploaded PDFs/Markdown, scraped Confluence pages,
and any other ingested doc. Chunks carry citation metadata (source_uri,
page, span) so retrievals can be cited downstream per PRD AC7.3.

The embedding column is `vector(1536)` when pgvector is installed; falls
back to `double precision[]` on Postgres without pgvector (e.g. Postgres 14
without the extension built). Cosine similarity is computed in Python in
both cases for portability; pgvector lets us add an HNSW index later for
scale.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    has_vector = bool(
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name='vector'"))
        .scalar()
    )

    op.create_table(
        "knowledge_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.Text, nullable=False),  # markdown | pdf | url | sf_kav
        sa.Column("uri", sa.Text, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("last_indexed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "uri", name="uq_knowledge_sources_tenant_uri"),
        schema="cogency",
    )

    # Embedding column type depends on pgvector availability; build the
    # Column lazily so we can keep the rest of the schema constant.
    embedding_col = (
        sa.Column("embedding", sa.dialects.postgresql.ARRAY(sa.Float))
        if not has_vector
        else None
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.knowledge_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("content_hash", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # embedding column added below — different type when pgvector present
        *( [embedding_col] if embedding_col is not None else [] ),
        sa.UniqueConstraint("source_id", "chunk_index", name="uq_knowledge_chunks_source_index"),
        schema="cogency",
    )

    if has_vector:
        op.execute("ALTER TABLE cogency.knowledge_chunks ADD COLUMN embedding vector(1536)")
        # HNSW for cosine — cheap to maintain, fast to query.
        op.execute(
            "CREATE INDEX ix_knowledge_chunks_embedding_hnsw "
            "ON cogency.knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )

    op.create_index(
        "ix_knowledge_chunks_tenant_active",
        "knowledge_chunks",
        ["tenant_id", "is_active"],
        schema="cogency",
    )
    op.create_index(
        "ix_knowledge_chunks_source",
        "knowledge_chunks",
        ["source_id"],
        schema="cogency",
    )
    op.create_index(
        "ix_knowledge_chunks_metadata_gin",
        "knowledge_chunks",
        ["metadata"],
        postgresql_using="gin",
        schema="cogency",
    )


def downgrade() -> None:
    op.drop_table("knowledge_chunks", schema="cogency")
    op.drop_table("knowledge_sources", schema="cogency")
