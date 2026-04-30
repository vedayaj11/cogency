"""Salesforce integration routes.

PRD §10.7:
    POST /v1/integrations/salesforce/connect
    POST /v1/integrations/salesforce/callback
    POST /v1/integrations/salesforce/disconnect
    GET  /v1/integrations/salesforce/sync_status
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient

from db.models.sf import SfCase, SfSyncState
from schemas import BackfillCasesInput, ConsumeCaseCDCInput

from app.config import Settings
from app.deps import db_session, settings_dep, temporal_client

router = APIRouter()


class SyncStatus(BaseModel):
    connected: bool
    last_run_at: datetime | None
    last_status: str | None
    watermark_ts: datetime | None
    cases_mirrored: int
    api_version: str


class BackfillRequest(BaseModel):
    sobject: str = "Case"
    since: datetime | None = None


class BackfillStarted(BaseModel):
    workflow_id: str
    run_id: str


@router.get("/sync_status", response_model=SyncStatus)
async def sync_status(
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> SyncStatus:
    state = (
        await session.execute(
            select(SfSyncState).where(
                SfSyncState.org_id == settings.cogency_dev_tenant_id,
                SfSyncState.sobject == "Case",
                SfSyncState.channel == "bulk",
            )
        )
    ).scalar_one_or_none()

    cases = await session.execute(
        select(SfCase).where(SfCase.org_id == settings.cogency_dev_tenant_id)
    )
    cases_mirrored = len(cases.scalars().all())

    has_creds = bool(
        settings.sf_client_id
        and (settings.sf_client_secret or settings.sf_jwt_private_key_path)
    )

    return SyncStatus(
        connected=has_creds and state is not None,
        last_run_at=state.last_run_at if state else None,
        last_status=state.last_status if state else None,
        watermark_ts=state.watermark_ts if state else None,
        cases_mirrored=cases_mirrored,
        api_version=settings.sf_api_version,
    )


@router.post("/backfill", response_model=BackfillStarted, status_code=202)
async def trigger_backfill(
    payload: BackfillRequest,
    settings: Settings = Depends(settings_dep),
    temporal: TemporalClient | None = Depends(temporal_client),
) -> BackfillStarted:
    if temporal is None:
        raise HTTPException(503, "temporal unavailable")
    if payload.sobject != "Case":
        raise HTTPException(400, "only Case backfill is implemented in MVP")

    workflow_id = f"sf-backfill-case-{settings.cogency_dev_tenant_id}-{uuid4()}"
    handle = await temporal.start_workflow(
        "BackfillCasesWorkflow",
        BackfillCasesInput(
            tenant_id=settings.cogency_dev_tenant_id, since=payload.since
        ),
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    return BackfillStarted(
        workflow_id=workflow_id, run_id=handle.first_execution_run_id or ""
    )


class StartCDCRequest(BaseModel):
    auto_trigger_aop: str | None = "case_manager"
    require_deployed: bool = True


class StartCDCResponse(BaseModel):
    workflow_id: str
    run_id: str


@router.post("/start_cdc", response_model=StartCDCResponse, status_code=202)
async def start_cdc(
    payload: StartCDCRequest = StartCDCRequest(),
    settings: Settings = Depends(settings_dep),
    temporal: TemporalClient | None = Depends(temporal_client),
) -> StartCDCResponse:
    """Start the CDC consumer workflow.

    Idempotent at the workflow_id level — calling twice with the same id
    returns the existing run rather than starting a duplicate.
    """
    if temporal is None:
        raise HTTPException(503, "temporal unavailable")

    workflow_id = f"cdc-case-{settings.cogency_dev_tenant_id}"
    handle = await temporal.start_workflow(
        "CDCConsumerWorkflow",
        ConsumeCaseCDCInput(
            tenant_id=settings.cogency_dev_tenant_id,
            auto_trigger_aop=payload.auto_trigger_aop,
            require_deployed=payload.require_deployed,
        ),
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
        # ID reuse policy: don't create a duplicate if one is already running
        id_reuse_policy=2,  # REJECT_DUPLICATE
    )
    return StartCDCResponse(
        workflow_id=workflow_id, run_id=handle.first_execution_run_id or ""
    )


class ConnectResponse(BaseModel):
    consent_url: str | None = None
    note: str


@router.post("/connect", response_model=ConnectResponse)
async def connect(settings: Settings = Depends(settings_dep)) -> ConnectResponse:
    """Initiate Salesforce OAuth Web Server flow (admin-blessed install).

    For MVP this returns the consent URL only; the callback handler that
    exchanges the code and persists tenant credentials lands in the next
    milestone. JWT Bearer handles subsequent integration-user auth.
    """
    if not settings.sf_client_id:
        raise HTTPException(400, "SF_CLIENT_ID not configured")
    redirect = "http://localhost:8000/v1/integrations/salesforce/callback"
    consent = (
        f"{settings.sf_login_url}/services/oauth2/authorize"
        f"?response_type=code&client_id={settings.sf_client_id}&redirect_uri={redirect}"
        "&scope=api+refresh_token+offline_access"
    )
    return ConnectResponse(
        consent_url=consent,
        note=(
            "MVP only returns the consent URL. The callback exchange handler "
            "lands in the next milestone."
        ),
    )
