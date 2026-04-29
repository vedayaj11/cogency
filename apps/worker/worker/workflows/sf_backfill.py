"""Salesforce backfill workflows.

`BackfillCasesWorkflow` — case-only path (kept for backwards compat).
`BackfillSObjectWorkflow` — single-sobject parametric.
`BackfillAllWorkflow` — fan-out across all default sobjects in parallel.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from schemas import (
        BackfillAllInput,
        BackfillAllResult,
        BackfillCasesInput,
        BackfillCasesResult,
        BackfillSObjectInput,
        BackfillSObjectResult,
    )
    from worker.activities.sf_backfill import backfill_cases, backfill_sobject


_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))


@workflow.defn
class BackfillCasesWorkflow:
    @workflow.run
    async def run(self, payload: BackfillCasesInput) -> BackfillCasesResult:
        return await workflow.execute_activity(
            backfill_cases,
            payload,
            start_to_close_timeout=timedelta(hours=2),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )


@workflow.defn
class BackfillSObjectWorkflow:
    @workflow.run
    async def run(self, payload: BackfillSObjectInput) -> BackfillSObjectResult:
        return await workflow.execute_activity(
            backfill_sobject,
            payload,
            start_to_close_timeout=timedelta(hours=2),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )


@workflow.defn
class BackfillAllWorkflow:
    """Fan out backfills across the requested sobjects in parallel."""

    @workflow.run
    async def run(self, payload: BackfillAllInput) -> BackfillAllResult:
        import asyncio

        async def one(sobject: str) -> BackfillSObjectResult:
            return await workflow.execute_activity(
                backfill_sobject,
                BackfillSObjectInput(tenant_id=payload.tenant_id, sobject=sobject),
                start_to_close_timeout=timedelta(hours=2),
                heartbeat_timeout=timedelta(minutes=5),
                retry_policy=_RETRY,
            )

        results = await asyncio.gather(*(one(s) for s in payload.sobjects))
        return BackfillAllResult(results=list(results))
