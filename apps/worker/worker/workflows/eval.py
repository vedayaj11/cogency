"""Eval run workflow — wraps the long-running execute_eval_run activity."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from schemas import EvalRunInput, EvalRunResult
    from worker.activities.eval import execute_eval_run


@workflow.defn
class RunEvalWorkflow:
    @workflow.run
    async def run(self, payload: EvalRunInput) -> EvalRunResult:
        return await workflow.execute_activity(
            execute_eval_run,
            payload,
            start_to_close_timeout=timedelta(hours=1),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=2, initial_interval=timedelta(seconds=5)
            ),
        )
