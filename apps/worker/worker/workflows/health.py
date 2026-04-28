from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from worker.activities.health import ping


@workflow.defn
class HealthWorkflow:
    @workflow.run
    async def run(self, message: str = "pong") -> str:
        return await workflow.execute_activity(
            ping, message, start_to_close_timeout=timedelta(seconds=10)
        )
