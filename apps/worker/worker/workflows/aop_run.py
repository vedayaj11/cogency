"""RunAOPWorkflow: thin wrapper over execute_aop_run.

The activity itself is long-lived (LLM tool loop), so the workflow's
responsibility is retry policy + heartbeats. We wrap a single activity for
MVP; richer workflows (pause-for-approval, sub-AOPs) come later.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from schemas import RunAOPInput, RunAOPResult
    from worker.activities.aop_run import execute_aop_run


@workflow.defn
class RunAOPWorkflow:
    @workflow.run
    async def run(self, payload: RunAOPInput) -> RunAOPResult:
        return await workflow.execute_activity(
            execute_aop_run,
            payload,
            start_to_close_timeout=timedelta(minutes=15),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=2, initial_interval=timedelta(seconds=5)
            ),
        )
