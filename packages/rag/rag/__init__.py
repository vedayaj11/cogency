"""Citation-grounded RAG for Cogency.

Layout:
- chunking.py    Token-aware paragraph-first chunker (lifted from llm-chatbot's
                 SimpleTextDocumentParser, async-friendly + carries metadata
                 per chunk so source_uri / page_num survive).
- embeddings.py  Async OpenAI text-embedding-3-large wrapper.
- store.py       PgVectorStore: cogency.knowledge_chunks store + cosine query.
                 Computed in Python for portability across pgvector / float[].
- ingest.py      End-to-end: parse → chunk → embed → upsert.
- parsers.py     PDF + Markdown drivers.
- types.py       Chunk, RetrievedChunk dataclasses.
"""

from rag.chunking import TokenChunker
from rag.embeddings import OpenAIEmbeddings, cosine_similarity
from rag.ingest import IngestResult, ingest_text
from rag.parsers import parse_markdown_file, parse_pdf_file
from rag.store import PgVectorStore
from rag.types import Chunk, RetrievedChunk

__all__ = [
    "TokenChunker",
    "OpenAIEmbeddings",
    "cosine_similarity",
    "PgVectorStore",
    "Chunk",
    "RetrievedChunk",
    "IngestResult",
    "ingest_text",
    "parse_markdown_file",
    "parse_pdf_file",
]
