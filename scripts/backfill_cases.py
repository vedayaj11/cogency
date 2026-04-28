"""One-shot CLI: trigger a Salesforce Case backfill via Temporal.

Usage:
    uv run python scripts/backfill_cases.py
    uv run python scripts/backfill_cases.py --since 2025-01-01T00:00:00Z

Reads SF_* and DATABASE_URL from .env. The Temporal worker must be running
(`make worker`) for the workflow to actually execute.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from uuid import uuid4

from temporalio.client import Client

from schemas import BackfillCasesInput
from worker.config import get_settings


async def main(since: datetime | None) -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_host, namespace=settings.temporal_namespace
    )
    payload = BackfillCasesInput(tenant_id=settings.cogency_dev_tenant_id, since=since)
    workflow_id = f"sf-backfill-case-cli-{uuid4()}"

    handle = await client.start_workflow(
        "BackfillCasesWorkflow",
        payload,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    print(f"started workflow_id={workflow_id} run_id={handle.first_execution_run_id}")
    print("waiting for completion (Ctrl-C to detach)...")
    result = await handle.result()
    print(f"done: {result.model_dump()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="ISO-8601 timestamp; only backfill changes after this")
    args = parser.parse_args()
    since = datetime.fromisoformat(args.since.replace("Z", "+00:00")) if args.since else None
    asyncio.run(main(since))
