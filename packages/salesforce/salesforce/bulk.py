"""Bulk API 2.0 client.

PRD §7.2: PK Chunking (chunkSize=100k) for backfill. Skeleton only — implement
the full lifecycle (createJob, uploadJobData, closeJob, poll status, fetch
results, deleteJob) as part of the sync workers milestone.
"""

from __future__ import annotations

from dataclasses import dataclass

from salesforce.auth import JWTBearerAuth


@dataclass
class BulkClient:
    auth: JWTBearerAuth

    async def submit_query_job(
        self,
        sobject: str,
        query: str,
        *,
        chunk_size: int = 100_000,
    ) -> str:
        """Create a Bulk 2.0 query job. Returns job_id."""
        # TODO(salesforce-sync): implement POST /services/data/vXX.X/jobs/query
        raise NotImplementedError

    async def poll_job(self, job_id: str) -> dict:
        # TODO(salesforce-sync)
        raise NotImplementedError

    async def fetch_results(self, job_id: str):
        """Yield CSV result chunks for streaming apply to local mirror."""
        # TODO(salesforce-sync)
        raise NotImplementedError
        yield  # pragma: no cover  # noqa: RUF100
