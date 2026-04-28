import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from worker.activities import backfill_cases, ping
from worker.config import get_settings
from worker.workflows import BackfillCasesWorkflow, HealthWorkflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cogency.worker")


async def run() -> None:
    settings = get_settings()
    log.info("connecting to temporal at %s", settings.temporal_host)
    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[HealthWorkflow, BackfillCasesWorkflow],
        activities=[ping, backfill_cases],
    )
    log.info("worker ready on task queue %s", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run())
