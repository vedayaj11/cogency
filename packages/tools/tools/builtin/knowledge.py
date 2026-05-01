"""Knowledge retrieval tool — citation-grounded RAG.

Returns chunks with `citation_id` so the AOP executor can require facts to
trace back to a chunk_id (PRD AC7.3). The shape of `citation_id` is a
12-char hex prefix of the chunk's UUID — short enough to inline as
`[cite:abc123def456]` without bloating the LLM context.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from rag import OpenAIEmbeddings, PgVectorStore

from tools.registry import Tool, ToolContext


class LookupKnowledgeInput(BaseModel):
    query: str = Field(description="Free-text question or topic. Will be embedded and matched against chunks via cosine similarity.")
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Filter out chunks below this cosine similarity score."
    )


class KnowledgeHit(BaseModel):
    citation_id: str
    source_uri: str | None
    title: str | None
    page_num: int | None
    chunk_index: int
    text: str
    score: float
    metadata: dict[str, Any] = {}


class LookupKnowledgeOutput(BaseModel):
    hits: list[KnowledgeHit]
    note: str | None = None


async def lookup_knowledge(
    ctx: ToolContext, p: LookupKnowledgeInput
) -> LookupKnowledgeOutput:
    if ctx.session is None:
        raise RuntimeError("lookup_knowledge requires a DB session in ToolContext")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return LookupKnowledgeOutput(
            hits=[], note="OPENAI_API_KEY not configured; cannot embed query"
        )
    model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

    embeddings = OpenAIEmbeddings(api_key=api_key, model=model)
    query_vec = await embeddings.embed_query(p.query)

    store = PgVectorStore(ctx.session)
    retrieved = await store.query_similar(
        tenant_id=ctx.tenant_id,
        query_embedding=query_vec,
        top_k=p.top_k,
        min_score=p.min_score,
    )

    hits = [
        KnowledgeHit(
            citation_id=r.citation_id,
            source_uri=r.metadata.get("source_uri"),
            title=r.metadata.get("title"),
            page_num=r.metadata.get("page_num"),
            chunk_index=r.chunk_index,
            text=r.text,
            score=round(r.score, 4),
            metadata=r.metadata,
        )
        for r in retrieved
    ]
    note: str | None = None
    if not hits:
        note = (
            "No chunks indexed yet for this tenant — ingest a knowledge "
            "source via POST /v1/knowledge/sources first."
        )
    return LookupKnowledgeOutput(hits=hits, note=note)


LOOKUP_KNOWLEDGE = Tool(
    name="lookup_knowledge",
    description=(
        "Search the knowledge base for chunks relevant to a query. Returns "
        "the top-k chunks with citation_ids the agent MUST cite when making "
        "factual claims about policy or procedure. Use this tool BEFORE "
        "drafting any reply that asserts a fact."
    ),
    required_scopes=["knowledge.read"],
    input_schema=LookupKnowledgeInput,
    output_schema=LookupKnowledgeOutput,
    func=lookup_knowledge,
    is_read_only=True,
)


__all__ = ["LOOKUP_KNOWLEDGE"]
