"""Ingest pipeline: parse → chunk → embed → upsert.

The driver functions are deliberately small and composable — `ingest_text`
is the workhorse that everything else funnels into. PDF/Markdown drivers
just produce (text, page_num) tuples and feed them in.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from rag.chunking import TokenChunker
from rag.embeddings import OpenAIEmbeddings
from rag.parsers import parse_markdown_file, parse_pdf_file
from rag.store import PgVectorStore
from rag.types import Chunk


@dataclass
class IngestResult:
    source_id: UUID
    chunks_written: int
    pages: int  # 0 for non-paginated sources (markdown)


async def ingest_text(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    embeddings: OpenAIEmbeddings,
    chunker: TokenChunker,
    type: str,
    uri: str,
    title: str | None,
    pages: list[tuple[str, int | None]],
    metadata: dict[str, Any] | None = None,
) -> IngestResult:
    """Workhorse: chunk + embed + upsert.

    `pages` is a list of `(page_text, page_num | None)` tuples — the parser
    upstream produces these. Each chunk inherits `source_uri`, `title`, and
    its `page_num` for citation.
    """
    base_meta = {
        "source_uri": uri,
        "source_type": type,
    }
    if title:
        base_meta["title"] = title
    if metadata:
        base_meta.update(metadata)

    all_chunks: list[Chunk] = []
    next_index = 0
    for page_text, page_num in pages:
        page_meta = dict(base_meta)
        if page_num is not None:
            page_meta["page_num"] = page_num
        page_chunks = chunker.split(page_text, base_metadata=page_meta)
        # Renumber chunk_index across pages so the unique constraint
        # (source_id, chunk_index) holds.
        for c in page_chunks:
            c.chunk_index = next_index
            next_index += 1
            all_chunks.append(c)

    if not all_chunks:
        # Still record the source so we know we tried.
        store = PgVectorStore(session)
        source = await store.upsert_source(
            tenant_id=tenant_id, type=type, uri=uri, title=title, metadata=base_meta
        )
        return IngestResult(source_id=source.id, chunks_written=0, pages=len(pages))

    # Embed all chunks in batches.
    texts = [c.text for c in all_chunks]
    vectors = await embeddings.embed_documents(texts)

    store = PgVectorStore(session)
    source = await store.upsert_source(
        tenant_id=tenant_id, type=type, uri=uri, title=title, metadata=base_meta
    )
    written = await store.upsert_chunks(
        tenant_id=tenant_id,
        source_id=source.id,
        chunks=all_chunks,
        embeddings=vectors,
    )
    return IngestResult(source_id=source.id, chunks_written=written, pages=len(pages))


async def ingest_markdown_file(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    embeddings: OpenAIEmbeddings,
    chunker: TokenChunker,
    path: str | Path,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> IngestResult:
    pages = list(parse_markdown_file(path))
    uri = f"file://{Path(path).resolve()}"
    return await ingest_text(
        session=session,
        tenant_id=tenant_id,
        embeddings=embeddings,
        chunker=chunker,
        type="markdown",
        uri=uri,
        title=title or Path(path).stem,
        pages=pages,
        metadata=metadata,
    )


async def ingest_pdf_file(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    embeddings: OpenAIEmbeddings,
    chunker: TokenChunker,
    path: str | Path,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> IngestResult:
    pages = list(parse_pdf_file(path))
    uri = f"file://{Path(path).resolve()}"
    return await ingest_text(
        session=session,
        tenant_id=tenant_id,
        embeddings=embeddings,
        chunker=chunker,
        type="pdf",
        uri=uri,
        title=title or Path(path).stem,
        pages=pages,
        metadata=metadata,
    )
