"""Salesforce backfill activities.

PRD §7.2: Bulk API 2.0 query w/ PK Chunking; ~2k records/sec; minimal API
quota cost. We watermark on SystemModstamp (PRD §7.3) — every backfill query
is bounded by `WHERE SystemModstamp > :watermark` so re-runs are incremental
even though the channel is "bulk".

`backfill_sobject` is the generic factory; per-sobject activities (cases,
emails, comments, tasks, knowledge) just plug in the SOQL field list and the
target repository.
"""

from __future__ import annotations

from datetime import datetime

from temporalio import activity

from db import (
    CaseCommentRepository,
    CaseRepository,
    EmailMessageRepository,
    KnowledgeRepository,
    SyncStateRepository,
    TaskRepository,
    async_session,
)
from db.repositories._base import MirrorUpsertRepository
from salesforce import parse_csv_chunk
from schemas import (
    BackfillAllInput,
    BackfillAllResult,
    BackfillCasesInput,
    BackfillCasesResult,
    BackfillSObjectInput,
    BackfillSObjectResult,
)

from worker.config import get_settings
from worker.sf import build_salesforce_client


# SOQL field lists per sobject — kept as constants so they're easy to audit
# and extend.
SOBJECT_FIELDS = {
    "Case": (
        "Id, CaseNumber, Subject, Description, Status, Priority, Origin, "
        "ContactId, AccountId, OwnerId, CreatedDate, SystemModstamp, IsDeleted"
    ),
    "EmailMessage": (
        "Id, ParentId, FromAddress, ToAddress, CcAddress, BccAddress, "
        "Subject, TextBody, HtmlBody, Status, Incoming, MessageDate, "
        "SystemModstamp, IsDeleted"
    ),
    "CaseComment": (
        "Id, ParentId, CommentBody, IsPublished, CreatedById, CreatedDate, "
        "SystemModstamp, IsDeleted"
    ),
    "Task": (
        "Id, WhatId, WhoId, OwnerId, Subject, Status, Priority, "
        "ActivityDate, Description, Type, IsClosed, SystemModstamp, IsDeleted"
    ),
    "KnowledgeArticleVersion": (
        "Id, KnowledgeArticleId, Title, Summary, UrlName, PublishStatus, "
        "ArticleType, Body, Language, SystemModstamp, IsDeleted"
    ),
}


def _build_query(
    sobject: str, since: datetime | None, extra_where: str | None
) -> str:
    fields = SOBJECT_FIELDS[sobject]
    where_parts: list[str] = []
    if since is not None:
        where_parts.append(
            f"SystemModstamp > {since.isoformat().replace('+00:00', 'Z')}"
        )
    if extra_where:
        where_parts.append(extra_where)
    where = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
    return f"SELECT {fields} FROM {sobject}{where} ORDER BY SystemModstamp ASC"


def _build_repository(sobject: str, session) -> MirrorUpsertRepository:
    if sobject == "Case":
        return CaseRepository(session)  # type: ignore[return-value]
    if sobject == "EmailMessage":
        return EmailMessageRepository(session)
    if sobject == "CaseComment":
        return CaseCommentRepository(session)
    if sobject == "Task":
        return TaskRepository(session)
    if sobject == "KnowledgeArticleVersion":
        return KnowledgeRepository(session)
    raise ValueError(f"unsupported sobject for backfill: {sobject}")


@activity.defn
async def backfill_sobject(payload: BackfillSObjectInput) -> BackfillSObjectResult:
    """Generic Bulk 2.0 backfill for any registered sobject."""
    settings = get_settings()
    sf = build_salesforce_client(settings)

    since = payload.since
    async with async_session(settings.database_url) as session:
        sync_repo = SyncStateRepository(session)
        if since is None:
            existing = await sync_repo.get(payload.tenant_id, payload.sobject, "bulk")
            since = existing.watermark_ts if existing else None

    soql = _build_query(payload.sobject, since, payload.soql_extra_where)
    activity.logger.info(
        "backfill.submit_job", extra={"sobject": payload.sobject, "soql": soql}
    )

    job_id = await sf.submit_query_job(soql)
    activity.heartbeat(f"submitted {payload.sobject} job {job_id}")

    job = await sf.wait_for_query_job(job_id, poll_interval=5.0)
    activity.logger.info(
        "backfill.job_complete",
        extra={"sobject": payload.sobject, "job_id": job_id, "state": job.get("state")},
    )

    rows_applied = 0
    max_modstamp: datetime | None = since

    async with async_session(settings.database_url) as session:
        repo = _build_repository(payload.sobject, session)
        sync_repo = SyncStateRepository(session)

        # CaseRepository has its own upsert_many signature; the generic
        # MirrorUpsertRepository.upsert_many is structurally identical.
        async for chunk in sf.iter_query_results(job_id):
            rows = list(parse_csv_chunk(chunk))
            if not rows:
                continue
            applied = await repo.upsert_many(payload.tenant_id, rows)
            rows_applied += applied
            for row in rows:
                ts = row.get("SystemModstamp")
                if ts:
                    parsed = datetime.fromisoformat(
                        ts.replace("Z", "+00:00").replace("+0000", "+00:00")
                    )
                    if max_modstamp is None or parsed > max_modstamp:
                        max_modstamp = parsed
            activity.heartbeat(
                f"{payload.sobject}: applied {rows_applied} rows so far"
            )

        await sync_repo.upsert(
            org_id=payload.tenant_id,
            sobject=payload.sobject,
            channel="bulk",
            watermark_ts=max_modstamp,
            last_status=f"completed:{rows_applied}",
        )

    try:
        await sf.delete_query_job(job_id)
    except Exception as e:
        activity.logger.warning(
            "backfill.delete_job_failed",
            extra={"sobject": payload.sobject, "error": str(e)},
        )

    return BackfillSObjectResult(
        sobject=payload.sobject,
        job_id=job_id,
        rows_applied=rows_applied,
        watermark_ts=max_modstamp,
    )


@activity.defn
async def backfill_cases(payload: BackfillCasesInput) -> BackfillCasesResult:
    """Backwards-compatible Case-specific backfill (delegates to the generic)."""
    result = await backfill_sobject(
        BackfillSObjectInput(
            tenant_id=payload.tenant_id,
            sobject="Case",
            since=payload.since,
            soql_extra_where=payload.soql_extra_where,
        )
    )
    return BackfillCasesResult(
        job_id=result.job_id,
        rows_applied=result.rows_applied,
        watermark_ts=result.watermark_ts,
    )
