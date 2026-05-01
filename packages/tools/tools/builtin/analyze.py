"""LLM-backed analyze tools.

For MVP these call OpenAI directly (the executor's LLMClient isn't passed
into ToolContext today). To keep tools self-contained, we instantiate a
short-lived AsyncOpenAI client per call. That's wasteful at scale; M7 will
hoist a shared client into ToolContext.
"""

from __future__ import annotations

import json
import os
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from db.models.sf import SfCase, SfCaseComment, SfEmailMessage
from rag import OpenAIEmbeddings, cosine_similarity

from tools.registry import Tool, ToolContext


# ---------- helper: short-lived OpenAI client ----------

def _client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return AsyncOpenAI(api_key=api_key)


def _model() -> str:
    return os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o")


# ---------- classify_case ----------

class ClassifyCaseInput(BaseModel):
    case_id: str
    subject: str | None = None
    description: str | None = None


class ClassifyCaseOutput(BaseModel):
    case_id: str
    category: Literal[
        "billing", "refund", "technical", "account", "complaint", "feature_request", "other"
    ]
    intent: str
    priority: Literal["Low", "Medium", "High", "Critical"]
    confidence: float = Field(ge=0, le=1)
    reasoning: str


async def classify_case(
    ctx: ToolContext, p: ClassifyCaseInput
) -> ClassifyCaseOutput:
    # Fall back to mirror lookup if subject/description weren't passed.
    subject = p.subject
    description = p.description
    if (subject is None or description is None) and ctx.session is not None:
        row = (
            await ctx.session.execute(
                select(SfCase).where(
                    SfCase.org_id == ctx.tenant_id, SfCase.id == p.case_id
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            subject = subject or row.subject
            description = description or row.description

    prompt = (
        "You are classifying a customer support case. Given the subject + "
        "description, return JSON with: category (billing|refund|technical|account|"
        "complaint|feature_request|other), intent (a short noun phrase), "
        "priority (Low|Medium|High|Critical), confidence (0..1), "
        "reasoning (one sentence). Only return JSON.\n\n"
        f"Subject: {subject or '(none)'}\n"
        f"Description: {description or '(none)'}"
    )
    resp = await _client().chat.completions.create(
        model=_model(),
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=400,
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    return ClassifyCaseOutput(
        case_id=p.case_id,
        category=parsed.get("category", "other"),
        intent=parsed.get("intent", ""),
        priority=parsed.get("priority", "Medium"),
        confidence=float(parsed.get("confidence", 0.5)),
        reasoning=parsed.get("reasoning", ""),
    )


CLASSIFY_CASE = Tool(
    name="classify_case",
    description="Classify a Case's category + intent + priority via LLM. Use during triage to decide which queue or AOP applies.",
    required_scopes=["case.read"],
    input_schema=ClassifyCaseInput,
    output_schema=ClassifyCaseOutput,
    func=classify_case,
    is_read_only=True,
)


# ---------- extract_sentiment ----------

class ExtractSentimentInput(BaseModel):
    case_id: str | None = None
    text: str | None = Field(
        default=None,
        description="Optional explicit text. If missing, sentiment is computed over the case description + comments.",
    )


class ExtractSentimentOutput(BaseModel):
    sentiment: float = Field(ge=-1, le=1)
    label: Literal["very_negative", "negative", "neutral", "positive", "very_positive"]
    reasoning: str


async def extract_sentiment(
    ctx: ToolContext, p: ExtractSentimentInput
) -> ExtractSentimentOutput:
    text = p.text
    if text is None and p.case_id and ctx.session is not None:
        row = (
            await ctx.session.execute(
                select(SfCase).where(
                    SfCase.org_id == ctx.tenant_id, SfCase.id == p.case_id
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            text = (row.subject or "") + "\n" + (row.description or "")
    if not text:
        return ExtractSentimentOutput(
            sentiment=0.0, label="neutral", reasoning="no text provided"
        )

    resp = await _client().chat.completions.create(
        model=_model(),
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Score the customer sentiment in this text from -1.0 (very negative) "
                    "to +1.0 (very positive). Return JSON: {sentiment, label, reasoning}.\n\n"
                    + text[:2000]
                ),
            }
        ],
        temperature=0.0,
        max_tokens=200,
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    score = float(parsed.get("sentiment", 0))
    label_map = (
        ("very_negative", -0.6),
        ("negative", -0.2),
        ("neutral", 0.2),
        ("positive", 0.6),
        ("very_positive", 1.01),
    )
    label = "neutral"
    for name, ceil in label_map:
        if score < ceil:
            label = name
            break
    return ExtractSentimentOutput(
        sentiment=max(-1.0, min(1.0, score)),
        label=label,  # type: ignore[arg-type]
        reasoning=parsed.get("reasoning", ""),
    )


EXTRACT_SENTIMENT = Tool(
    name="extract_sentiment",
    description="Score customer sentiment as a float in [-1, 1] with a label. Reads case text by id, or scores explicit text.",
    required_scopes=["case.read"],
    input_schema=ExtractSentimentInput,
    output_schema=ExtractSentimentOutput,
    func=extract_sentiment,
    is_read_only=True,
)


# ---------- summarize_case ----------

class SummarizeCaseInput(BaseModel):
    case_id: str
    max_words: int = Field(default=200, ge=50, le=600)


class SummarizeCaseOutput(BaseModel):
    case_id: str
    summary: str


async def summarize_case(
    ctx: ToolContext, p: SummarizeCaseInput
) -> SummarizeCaseOutput:
    if ctx.session is None:
        raise RuntimeError("summarize_case requires a DB session")
    case = (
        await ctx.session.execute(
            select(SfCase).where(
                SfCase.org_id == ctx.tenant_id, SfCase.id == p.case_id
            )
        )
    ).scalar_one_or_none()
    if case is None:
        return SummarizeCaseOutput(case_id=p.case_id, summary="(case not found)")

    comments = list(
        (
            await ctx.session.execute(
                select(SfCaseComment).where(
                    SfCaseComment.org_id == ctx.tenant_id,
                    SfCaseComment.parent_id == p.case_id,
                )
            )
        ).scalars().all()
    )
    emails = list(
        (
            await ctx.session.execute(
                select(SfEmailMessage).where(
                    SfEmailMessage.org_id == ctx.tenant_id,
                    SfEmailMessage.parent_id == p.case_id,
                )
            )
        ).scalars().all()
    )

    feed = [
        f"# Case {case.case_number or case.id}",
        f"Status: {case.status}, Priority: {case.priority}",
        f"Subject: {case.subject}",
        f"Description: {case.description}",
        "## Comments",
        *(f"- {c.comment_body or ''}" for c in comments[:20]),
        "## Emails",
        *(f"- {'IN' if e.incoming else 'OUT'}: {e.subject or ''} | {(e.text_body or '')[:200]}" for e in emails[:20]),
    ]
    blob = "\n".join(feed)[:8000]

    resp = await _client().chat.completions.create(
        model=_model(),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Summarize this case in <= {p.max_words} words. Cover: "
                    f"what the customer wants, what's been done, what's blocking. "
                    f"No preamble.\n\n{blob}"
                ),
            }
        ],
        temperature=0.1,
        max_tokens=800,
    )
    return SummarizeCaseOutput(
        case_id=p.case_id, summary=resp.choices[0].message.content or ""
    )


SUMMARIZE_CASE = Tool(
    name="summarize_case",
    description="Roll up the full case (description + comments + emails) into a short summary via LLM. Always call this before drafting a customer reply.",
    required_scopes=["case.read"],
    input_schema=SummarizeCaseInput,
    output_schema=SummarizeCaseOutput,
    func=summarize_case,
    is_read_only=True,
)


# ---------- search_similar_cases ----------

class SearchSimilarCasesInput(BaseModel):
    case_id: str
    limit: int = Field(default=5, ge=1, le=20)


class SimilarCaseItem(BaseModel):
    id: str
    case_number: str | None
    subject: str | None
    status: str | None


class SearchSimilarCasesOutput(BaseModel):
    items: list[SimilarCaseItem]
    method: Literal["text", "semantic"]


async def _ensure_embedding(ctx: ToolContext, case: SfCase) -> list[float] | None:
    """Lazy-populate `sf.case.embedding` if missing.

    Embeds (subject + description) — same shape as ingestion. We avoid a
    bulk backfill activity for now; embeddings get populated as
    search_similar_cases is called against the case for the first time.
    """
    if case.embedding:
        return list(case.embedding)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    text = ((case.subject or "") + "\n" + (case.description or "")).strip()
    if not text:
        return None
    embeddings = OpenAIEmbeddings(api_key=api_key, model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"))
    vec = await embeddings.embed_query(text)
    case.embedding = vec
    if ctx.session is not None:
        await ctx.session.commit()
    return vec


async def search_similar_cases(
    ctx: ToolContext, p: SearchSimilarCasesInput
) -> SearchSimilarCasesOutput:
    """Vector-cosine search over `sf.case.embedding`. Falls back to a
    text-keyword match if the source case has no text or embeddings are
    unavailable. Embeddings populate lazily — the first call against a
    case backfills its row."""
    if ctx.session is None:
        raise RuntimeError("search_similar_cases requires a DB session")
    case = (
        await ctx.session.execute(
            select(SfCase).where(
                SfCase.org_id == ctx.tenant_id, SfCase.id == p.case_id
            )
        )
    ).scalar_one_or_none()
    if case is None or not case.subject:
        return SearchSimilarCasesOutput(items=[], method="text")

    query_vec = await _ensure_embedding(ctx, case)
    if query_vec is not None:
        # Vector path — pull every other case with an embedding for this
        # tenant, score in Python, return top-k.
        stmt = (
            select(SfCase)
            .where(
                SfCase.org_id == ctx.tenant_id,
                SfCase.id != p.case_id,
                SfCase.is_deleted.is_(False),
                SfCase.embedding.is_not(None),
            )
        )
        rows = list((await ctx.session.execute(stmt)).scalars().all())
        scored = []
        for r in rows:
            s = cosine_similarity(query_vec, list(r.embedding or []))
            scored.append((s, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: p.limit]
        if top:
            return SearchSimilarCasesOutput(
                items=[
                    SimilarCaseItem(
                        id=r.id,
                        case_number=r.case_number,
                        subject=r.subject,
                        status=r.status,
                    )
                    for _s, r in top
                ],
                method="semantic",
            )

    # Fallback: keyword overlap on subject.
    keywords = [w for w in case.subject.split() if len(w) >= 4][:5]
    if not keywords:
        return SearchSimilarCasesOutput(items=[], method="text")
    preds = [SfCase.subject.ilike(f"%{w}%") for w in keywords]
    stmt = (
        select(SfCase)
        .where(
            SfCase.org_id == ctx.tenant_id,
            SfCase.id != p.case_id,
            SfCase.is_deleted.is_(False),
            or_(*preds),
        )
        .limit(p.limit)
    )
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return SearchSimilarCasesOutput(
        items=[
            SimilarCaseItem(
                id=r.id,
                case_number=r.case_number,
                subject=r.subject,
                status=r.status,
            )
            for r in rows
        ],
        method="text",
    )


SEARCH_SIMILAR_CASES = Tool(
    name="search_similar_cases",
    description="Find prior cases with similar text to the given case. Text-keyword match in M6; semantic cosine over case embeddings lands in M7.",
    required_scopes=["case.read"],
    input_schema=SearchSimilarCasesInput,
    output_schema=SearchSimilarCasesOutput,
    func=search_similar_cases,
    is_read_only=True,
)


# ---------- detect_duplicate_cases ----------

class DetectDuplicatesInput(BaseModel):
    case_id: str


class DetectDuplicatesOutput(BaseModel):
    case_id: str
    duplicates: list[SimilarCaseItem]
    note: str


async def detect_duplicate_cases(
    ctx: ToolContext, p: DetectDuplicatesInput
) -> DetectDuplicatesOutput:
    """Heuristic: same contact + same subject (case-insensitive) within 7 days
    counts as a candidate duplicate. Embedding-based detection lands in M7."""
    if ctx.session is None:
        raise RuntimeError("detect_duplicate_cases requires a DB session")
    case = (
        await ctx.session.execute(
            select(SfCase).where(
                SfCase.org_id == ctx.tenant_id, SfCase.id == p.case_id
            )
        )
    ).scalar_one_or_none()
    if case is None or not case.contact_id or not case.subject:
        return DetectDuplicatesOutput(
            case_id=p.case_id,
            duplicates=[],
            note="case missing contact_id or subject; cannot detect",
        )

    from datetime import timedelta

    from datetime import UTC

    cutoff = (case.created_date or case.system_modstamp) - timedelta(days=7)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)

    stmt = (
        select(SfCase)
        .where(
            SfCase.org_id == ctx.tenant_id,
            SfCase.contact_id == case.contact_id,
            SfCase.id != p.case_id,
            SfCase.subject.ilike(case.subject),
            SfCase.system_modstamp >= cutoff,
        )
        .limit(10)
    )
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    return DetectDuplicatesOutput(
        case_id=p.case_id,
        duplicates=[
            SimilarCaseItem(
                id=r.id,
                case_number=r.case_number,
                subject=r.subject,
                status=r.status,
            )
            for r in rows
        ],
        note="heuristic: same contact + same subject within 7 days; promote to embedding cosine in M7",
    )


DETECT_DUPLICATE_CASES = Tool(
    name="detect_duplicate_cases",
    description="Identify candidate duplicate cases for a given case. Heuristic in M6, semantic in M7.",
    required_scopes=["case.read"],
    input_schema=DetectDuplicatesInput,
    output_schema=DetectDuplicatesOutput,
    func=detect_duplicate_cases,
    is_read_only=True,
)


__all__ = [
    "CLASSIFY_CASE",
    "EXTRACT_SENTIMENT",
    "SUMMARIZE_CASE",
    "SEARCH_SIMILAR_CASES",
    "DETECT_DUPLICATE_CASES",
]
