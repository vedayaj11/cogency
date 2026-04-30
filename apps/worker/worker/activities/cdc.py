"""Long-running CDC consumer activity.

Subscribes to Salesforce Pub/Sub `/data/CaseChangeEvent`, upserts each event
into the local mirror (so reads from the agent stay sub-100ms), persists the
replay_id after every commit, and optionally auto-triggers the
`case_manager` AOP on each CREATE event so the system is genuinely
autonomous (every new SF case gets worked without human intervention).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from temporalio import activity
from temporalio.client import Client as TemporalClient

from db import (
    AOPRepository,
    AOPVersion,
    CaseRepository,
    SyncStateRepository,
    async_session,
)
from salesforce import CDCEvent, PubSubConsumer
from schemas import ConsumeCaseCDCInput, ConsumeCaseCDCResult, RunAOPInput

from worker.config import get_settings
from worker.sf import build_salesforce_client


# Salesforce Pub/Sub Avro for ChangeEventHeader.changeType is a string union;
# values relevant for our trigger logic.
_CREATE_TYPES = {"CREATE"}


def _cdc_to_case_row(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Map an Avro-decoded CaseChangeEvent payload to a row suitable for
    `CaseRepository.upsert_many`. Returns None if the event isn't useful
    (e.g. GAP_*, no record id)."""
    header = payload.get("ChangeEventHeader") or {}
    record_ids = header.get("recordIds") or []
    if not record_ids:
        return None
    case_id = str(record_ids[0])
    change_type = str(header.get("changeType", ""))
    if change_type.startswith("GAP_"):
        return None

    # The payload contains the changed fields directly under the top-level.
    # We pass through the union of stock fields; CaseRepository routes the
    # rest to custom_fields. We also keep IsDeleted in sync for DELETEs.
    row: dict[str, Any] = {
        "Id": case_id,
        "CaseNumber": payload.get("CaseNumber"),
        "Subject": payload.get("Subject"),
        "Description": payload.get("Description"),
        "Status": payload.get("Status"),
        "Priority": payload.get("Priority"),
        "Origin": payload.get("Origin"),
        "ContactId": payload.get("ContactId"),
        "AccountId": payload.get("AccountId"),
        "OwnerId": payload.get("OwnerId"),
        "CreatedDate": payload.get("CreatedDate"),
        "SystemModstamp": payload.get("LastModifiedDate") or datetime.now(UTC).isoformat(),
        "IsDeleted": change_type == "DELETE",
    }
    # Drop None values so we don't blat existing fields with NULL on partial
    # updates.
    return {k: v for k, v in row.items() if v is not None}


async def _resolve_aop_version_id(tenant_id, aop_name: str, require_deployed: bool):
    settings = get_settings()
    async with async_session(settings.database_url) as session:
        repo = AOPRepository(session)
        aop = await repo.get_by_name(tenant_id, aop_name)
        if aop is None:
            return None
        if aop.current_version_id is not None:
            return aop.current_version_id
        if require_deployed:
            return None
        latest = await repo.latest_version(aop.id)
        return latest.id if latest else None


@activity.defn
async def consume_case_cdc(payload: ConsumeCaseCDCInput) -> ConsumeCaseCDCResult:
    settings = get_settings()
    sf_client = build_salesforce_client(settings)
    consumer = PubSubConsumer(auth=sf_client.auth, endpoint=settings.sf_pubsub_endpoint)

    # Resume from last committed replay_id.
    last_replay_id: bytes | None = None
    async with async_session(settings.database_url) as session:
        sync_repo = SyncStateRepository(session)
        existing = await sync_repo.get(payload.tenant_id, "Case", "cdc")
        if existing and existing.cdc_replay_id:
            last_replay_id = existing.cdc_replay_id

    activity.logger.info(
        "cdc.subscribe",
        extra={"topic": payload.topic, "resume_from_replay": bool(last_replay_id)},
    )

    # Pre-resolve auto-trigger AOP version id (re-resolved on the fly per
    # event so newly-deployed AOPs are picked up without a restart).
    auto_aop_name = payload.auto_trigger_aop

    temporal_client = await TemporalClient.connect(
        settings.temporal_host, namespace=settings.temporal_namespace
    )

    events_processed = 0
    runs_triggered = 0

    async for event in consumer.subscribe(
        payload.topic,
        replay_id=last_replay_id,
        batch_size=payload.batch_size,
        tenant_id=str(payload.tenant_id),
    ):
        events_processed += 1
        last_replay_id = event.replay_id

        # 1. Upsert into mirror
        row = _cdc_to_case_row(event.payload)
        if row is not None:
            async with async_session(settings.database_url) as session:
                case_repo = CaseRepository(session)
                await case_repo.upsert_many(payload.tenant_id, [row])

        # 2. Persist replay_id immediately (after the upsert commits)
        async with async_session(settings.database_url) as session:
            sync_repo = SyncStateRepository(session)
            await sync_repo.upsert(
                org_id=payload.tenant_id,
                sobject="Case",
                channel="cdc",
                cdc_replay_id=last_replay_id,
                last_status=f"streaming:{events_processed}",
            )

        activity.heartbeat(
            f"event {events_processed}: {event.change_type} {event.record_ids}"
        )

        # 3. Auto-trigger case_manager on CREATE
        if (
            auto_aop_name
            and event.change_type in _CREATE_TYPES
            and event.record_ids
            # Skip our own writes (changeOrigin set by the integration user)
            and "client=PubSub" not in event.change_origin
        ):
            version_id = await _resolve_aop_version_id(
                payload.tenant_id, auto_aop_name, payload.require_deployed
            )
            if version_id is None:
                activity.logger.info(
                    "cdc.auto_trigger_skipped",
                    extra={"reason": "aop_not_deployed", "aop": auto_aop_name},
                )
                continue
            for case_id in event.record_ids:
                workflow_id = f"aop-run-{auto_aop_name}-{case_id}-cdc-{uuid4()}"
                try:
                    await temporal_client.start_workflow(
                        "RunAOPWorkflow",
                        RunAOPInput(
                            tenant_id=payload.tenant_id,
                            aop_version_id=version_id,
                            case_id=case_id,
                        ),
                        id=workflow_id,
                        task_queue=settings.temporal_task_queue,
                    )
                    runs_triggered += 1
                    activity.logger.info(
                        "cdc.auto_trigger_started",
                        extra={"workflow_id": workflow_id, "case_id": case_id},
                    )
                except Exception as e:
                    activity.logger.warning(
                        "cdc.auto_trigger_failed",
                        extra={"case_id": case_id, "error": str(e)},
                    )

    return ConsumeCaseCDCResult(
        events_processed=events_processed,
        last_replay_id_hex=last_replay_id.hex() if last_replay_id else None,
        runs_triggered=runs_triggered,
    )
