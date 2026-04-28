"""Salesforce backfill activities.

PRD §7.2: Bulk API 2.0 query w/ PK Chunking; ~2k records/sec; minimal API
quota cost. We watermark on SystemModstamp (PRD §7.3) — every backfill query
is bounded by `WHERE SystemModstamp > :watermark` so re-runs are incremental
even though the channel is "bulk".
"""

from __future__ import annotations

from datetime import datetime

from temporalio import activity

from db import CaseRepository, SyncStateRepository, async_session
from salesforce import parse_csv_chunk
from schemas import BackfillCasesInput, BackfillCasesResult

from worker.config import get_settings
from worker.sf import build_salesforce_client

CASE_FIELDS = (
    "Id, CaseNumber, Subject, Description, Status, Priority, Origin, "
    "ContactId, AccountId, OwnerId, CreatedDate, SystemModstamp, IsDeleted"
)


def _build_query(since: datetime | None, extra_where: str | None) -> str:
    where_parts: list[str] = []
    if since is not None:
        where_parts.append(f"SystemModstamp > {since.isoformat().replace('+00:00', 'Z')}")
    if extra_where:
        where_parts.append(extra_where)
    where = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
    return f"SELECT {CASE_FIELDS} FROM Case{where} ORDER BY SystemModstamp ASC"


@activity.defn
async def backfill_cases(payload: BackfillCasesInput) -> BackfillCasesResult:
    settings = get_settings()
    sf = build_salesforce_client(settings)

    since = payload.since
    async with async_session(settings.database_url) as session:
        sync_repo = SyncStateRepository(session)
        if since is None:
            existing = await sync_repo.get(payload.tenant_id, "Case", "bulk")
            since = existing.watermark_ts if existing else None

    soql = _build_query(since, payload.soql_extra_where)
    activity.logger.info("backfill.submit_job", extra={"soql": soql})

    job_id = await sf.submit_query_job(soql)
    activity.heartbeat(f"submitted job {job_id}")

    job = await sf.wait_for_query_job(job_id, poll_interval=5.0)
    activity.logger.info("backfill.job_complete", extra={"job_id": job_id, "job": job})

    rows_applied = 0
    max_modstamp: datetime | None = since

    async with async_session(settings.database_url) as session:
        case_repo = CaseRepository(session)
        sync_repo = SyncStateRepository(session)

        async for chunk in sf.iter_query_results(job_id):
            rows = list(parse_csv_chunk(chunk))
            if not rows:
                continue
            applied = await case_repo.upsert_many(payload.tenant_id, rows)
            rows_applied += applied
            for row in rows:
                ts = row.get("SystemModstamp")
                if ts:
                    parsed = datetime.fromisoformat(
                        ts.replace("Z", "+00:00").replace("+0000", "+00:00")
                    )
                    if max_modstamp is None or parsed > max_modstamp:
                        max_modstamp = parsed
            activity.heartbeat(f"applied {rows_applied} rows so far")

        await sync_repo.upsert(
            org_id=payload.tenant_id,
            sobject="Case",
            channel="bulk",
            watermark_ts=max_modstamp,
            last_status=f"completed:{rows_applied}",
        )

    try:
        await sf.delete_query_job(job_id)
    except Exception as e:
        activity.logger.warning("backfill.delete_job_failed", extra={"error": str(e)})

    return BackfillCasesResult(
        job_id=job_id, rows_applied=rows_applied, watermark_ts=max_modstamp
    )
