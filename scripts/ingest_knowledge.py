"""Ingest a Markdown or PDF file into the knowledge base.

Usage:
    uv run python scripts/ingest_knowledge.py aops/knowledge/refund_policy.md
    uv run python scripts/ingest_knowledge.py path/to/file.pdf --title "Onboarding Guide"
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from db import async_session
from rag import (
    OpenAIEmbeddings,
    TokenChunker,
)
from rag.ingest import ingest_markdown_file, ingest_pdf_file

from app.config import get_settings  # type: ignore[import-not-found]


async def main(path: Path, title: str | None) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY not set in .env")

    chunker = TokenChunker()
    embeddings = OpenAIEmbeddings(
        api_key=settings.openai_api_key, model=settings.openai_embedding_model
    )

    async with async_session(settings.database_url) as session:
        if path.suffix.lower() == ".pdf":
            result = await ingest_pdf_file(
                session=session,
                tenant_id=settings.cogency_dev_tenant_id,
                embeddings=embeddings,
                chunker=chunker,
                path=path,
                title=title,
            )
        else:
            result = await ingest_markdown_file(
                session=session,
                tenant_id=settings.cogency_dev_tenant_id,
                embeddings=embeddings,
                chunker=chunker,
                path=path,
                title=title,
            )

    print(
        f"ingested source_id={result.source_id} "
        f"chunks_written={result.chunks_written} pages={result.pages}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()
    asyncio.run(main(args.path, args.title))
