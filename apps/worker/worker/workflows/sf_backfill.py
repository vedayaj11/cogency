"""Salesforce backfill orchestration workflow.

Runs the Bulk 2.0 backfill activity for Case (and, in v2, the rest of §7.7).
Idempotent: a fresh execution picks up where the previous one left off via
sf_sync_state's watermark_ts.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from schemas import BackfillCasesInput, BackfillCasesResult
    from worker.activities.sf_backfill import backfill_cases


@workflow.defn
class BackfillCasesWorkflow:
    @workflow.run
    async def run(self, payload: BackfillCasesInput) -> BackfillCasesResult:
        return await workflow.execute_activity(
            backfill_cases,
            payload,
            start_to_close_timeout=timedelta(hours=2),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5)),
        )
