"""CDC consumer workflow.

Wraps `consume_case_cdc` with a long start_to_close timeout (the activity
streams until cancelled) and a retry policy that reconnects on failure.

The activity is heartbeating; if the worker dies mid-stream, Temporal sees
the heartbeat timeout and restarts the activity, which resumes from the
last persisted `replay_id` via `SyncStateRepository`.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from schemas import ConsumeCaseCDCInput, ConsumeCaseCDCResult
    from worker.activities.cdc import consume_case_cdc


@workflow.defn
class CDCConsumerWorkflow:
    @workflow.run
    async def run(self, payload: ConsumeCaseCDCInput) -> ConsumeCaseCDCResult:
        return await workflow.execute_activity(
            consume_case_cdc,
            payload,
            # Long-running consumer: 7 days before the activity is forcibly
            # restarted. In practice it heartbeats every event so a healthy
            # stream stays alive much longer.
            start_to_close_timeout=timedelta(days=7),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=0,  # retry forever
                initial_interval=timedelta(seconds=5),
                maximum_interval=timedelta(minutes=2),
                backoff_coefficient=2.0,
            ),
        )
