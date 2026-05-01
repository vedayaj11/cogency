"""Knowledge ingestion + search endpoints (PRD §10.6).

PRD spec:
    POST /v1/knowledge/sources           Upload a source (or pass URL)
    DELETE /v1/knowledge/sources/{id}    Soft-delete + deactivate chunks
    POST /v1/knowledge/sources/{id}/reindex
    POST /v1/knowledge/search            Hybrid search (text + semantic)

For M7 we implement add-by-content (POST raw text), add-by-path (server-
local file), search, and soft-delete. URL-fetching + Confluence connector
ingestion lands in M8.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.knowledge import KnowledgeChunk, KnowledgeSource
from rag import (
    OpenAIEmbeddings,
    PgVectorStore,
    TokenChunker,
    ingest_text,
)
from rag.parsers import parse_markdown_file, parse_pdf_file

from app.config import Settings
from app.deps import db_session, settings_dep

router = APIRouter()


def _embeddings(settings: Settings) -> OpenAIEmbeddings:
    if not settings.openai_api_key:
        raise HTTPException(503, "OPENAI_API_KEY not configured")
    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )


# ---------- list ----------

class KnowledgeSourceItem(BaseModel):
    id: UUID
    type: str
    uri: str
    title: str | None
    chunks_count: int
    last_indexed_at: str | None


class KnowledgeSourceListResponse(BaseModel):
    items: list[KnowledgeSourceItem]


@router.get("/v1/knowledge/sources", response_model=KnowledgeSourceListResponse)
async def list_sources(
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> KnowledgeSourceListResponse:
    sources = list(
        (
            await session.execute(
                select(KnowledgeSource)
                .where(KnowledgeSource.tenant_id == settings.cogency_dev_tenant_id)
                .order_by(desc(KnowledgeSource.last_indexed_at))
            )
        )
        .scalars()
        .all()
    )

    if sources:
        from sqlalchemy import func as _func

        counts = dict(
            (
                await session.execute(
                    select(KnowledgeChunk.source_id, _func.count())
                    .where(
                        KnowledgeChunk.source_id.in_([s.id for s in sources]),
                        KnowledgeChunk.is_active.is_(True),
                    )
                    .group_by(KnowledgeChunk.source_id)
                )
            ).all()
        )
    else:
        counts = {}

    return KnowledgeSourceListResponse(
        items=[
            KnowledgeSourceItem(
                id=s.id,
                type=s.type,
                uri=s.uri,
                title=s.title,
                chunks_count=counts.get(s.id, 0),
                last_indexed_at=s.last_indexed_at.isoformat() if s.last_indexed_at else None,
            )
            for s in sources
        ]
    )


# ---------- ingest by raw text ----------

class IngestTextRequest(BaseModel):
    type: str = Field(default="markdown", description="markdown | text | pdf | url")
    uri: str = Field(description="Stable identifier (e.g. file path, URL, doc-id).")
    title: str | None = None
    text: str = Field(description="Raw document content. For PDFs, use POST /v1/knowledge/sources/from_path.")
    metadata: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    source_id: UUID
    chunks_written: int
    pages: int


@router.post("/v1/knowledge/sources", response_model=IngestResponse)
async def ingest_by_text(
    payload: IngestTextRequest,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> IngestResponse:
    embeddings = _embeddings(settings)
    chunker = TokenChunker()
    result = await ingest_text(
        session=session,
        tenant_id=settings.cogency_dev_tenant_id,
        embeddings=embeddings,
        chunker=chunker,
        type=payload.type,
        uri=payload.uri,
        title=payload.title,
        pages=[(payload.text, None)],
        metadata=payload.metadata,
    )
    return IngestResponse(
        source_id=result.source_id,
        chunks_written=result.chunks_written,
        pages=result.pages,
    )


# ---------- ingest by server-local path ----------

class IngestFromPathRequest(BaseModel):
    path: str = Field(description="Absolute path on the API server to a .md / .txt / .pdf file.")
    type: str | None = None  # auto-detected from extension if omitted
    title: str | None = None
    metadata: dict[str, Any] | None = None


@router.post("/v1/knowledge/sources/from_path", response_model=IngestResponse)
async def ingest_by_path(
    payload: IngestFromPathRequest,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> IngestResponse:
    from pathlib import Path

    p = Path(payload.path)
    if not p.exists():
        raise HTTPException(404, f"path not found: {payload.path}")

    embeddings = _embeddings(settings)
    chunker = TokenChunker()

    detected_type = payload.type or (
        "pdf" if p.suffix.lower() == ".pdf" else "markdown"
    )
    if detected_type == "pdf":
        pages = list(parse_pdf_file(p))
    else:
        pages = list(parse_markdown_file(p))

    uri = f"file://{p.resolve()}"
    result = await ingest_text(
        session=session,
        tenant_id=settings.cogency_dev_tenant_id,
        embeddings=embeddings,
        chunker=chunker,
        type=detected_type,
        uri=uri,
        title=payload.title or p.stem,
        pages=pages,
        metadata=payload.metadata,
    )
    return IngestResponse(
        source_id=result.source_id,
        chunks_written=result.chunks_written,
        pages=result.pages,
    )


# ---------- search ----------

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchHit(BaseModel):
    citation_id: str
    source_id: UUID
    chunk_index: int
    text: str
    score: float
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    hits: list[SearchHit]


@router.post("/v1/knowledge/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> SearchResponse:
    embeddings = _embeddings(settings)
    query_vec = await embeddings.embed_query(payload.query)
    store = PgVectorStore(session)
    retrieved = await store.query_similar(
        tenant_id=settings.cogency_dev_tenant_id,
        query_embedding=query_vec,
        top_k=payload.top_k,
        min_score=payload.min_score,
    )
    return SearchResponse(
        hits=[
            SearchHit(
                citation_id=r.citation_id,
                source_id=r.source_id,
                chunk_index=r.chunk_index,
                text=r.text,
                score=round(r.score, 4),
                metadata=r.metadata,
            )
            for r in retrieved
        ]
    )


# ---------- soft delete ----------

@router.delete("/v1/knowledge/sources/{source_id}")
async def delete_source(
    source_id: UUID,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> dict[str, str]:
    source = await session.get(KnowledgeSource, source_id)
    if source is None or source.tenant_id != settings.cogency_dev_tenant_id:
        raise HTTPException(404, "source not found")
    store = PgVectorStore(session)
    deactivated = await store.deactivate_source(source_id=source.id)
    return {"status": "deactivated", "chunks_affected": str(deactivated)}
