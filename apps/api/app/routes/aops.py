"""AOP authoring + run endpoints.

PRD §10.2:
    POST   /v1/aops                          Create or upsert AOP from source
    POST   /v1/aops/{name}/versions          Add a new version
    POST   /v1/aops/{name}/versions/{v}/deploy
    POST   /v1/aop_runs                      Manual run trigger
    GET    /v1/aop_runs/{id}                 Run status + steps
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient

from sqlalchemy import desc, select

from aop import compile_aop, parse_aop_source
from aop.compiler import CompileError
from db import AOPRepository, AOPRunRepository
from db.models.aop import AOP, AOPRun, AOPVersion
from schemas import (
    AOPCreateRequest,
    AOPCreateResponse,
    AOPRunSummary,
    RunAOPInput,
)
from tools import build_default_registry

from app.config import Settings
from app.deps import db_session, settings_dep, temporal_client

router = APIRouter()


class AOPListItem(BaseModel):
    id: UUID
    name: str
    description: str | None
    current_version_id: UUID | None
    current_version_number: int | None
    versions_count: int


class AOPListResponse(BaseModel):
    items: list[AOPListItem]


@router.get("/v1/aops", response_model=AOPListResponse)
async def list_aops(
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> AOPListResponse:
    stmt = (
        select(AOP)
        .where(AOP.tenant_id == settings.cogency_dev_tenant_id)
        .order_by(AOP.name)
    )
    aops = list((await session.execute(stmt)).scalars().all())

    items: list[AOPListItem] = []
    for a in aops:
        versions = list(
            (
                await session.execute(
                    select(AOPVersion)
                    .where(AOPVersion.aop_id == a.id)
                    .order_by(desc(AOPVersion.version_number))
                )
            ).scalars().all()
        )
        current = next(
            (v for v in versions if v.id == a.current_version_id), versions[0] if versions else None
        )
        items.append(
            AOPListItem(
                id=a.id,
                name=a.name,
                description=a.description,
                current_version_id=a.current_version_id,
                current_version_number=current.version_number if current else None,
                versions_count=len(versions),
            )
        )
    return AOPListResponse(items=items)


@router.post("/v1/aops", response_model=AOPCreateResponse)
async def upsert_aop(
    payload: AOPCreateRequest,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> AOPCreateResponse:
    try:
        aop = parse_aop_source(payload.source_md)
    except Exception as e:
        raise HTTPException(400, f"AOP source parse error: {e}") from e

    if aop.name != payload.name:
        raise HTTPException(
            400,
            f"AOP name mismatch: payload.name='{payload.name}' but source declares '{aop.name}'",
        )

    registry = build_default_registry()
    granted_scopes = sorted({s for t in registry.tools.values() for s in t.required_scopes})

    compile_errors: list[str] = []
    try:
        compile_aop(aop, available_tools=registry.names(), granted_scopes=granted_scopes)
    except CompileError as e:
        compile_errors = e.errors

    repo = AOPRepository(session)
    aop_row = await repo.upsert_aop(
        tenant_id=settings.cogency_dev_tenant_id,
        name=aop.name,
        description=aop.description,
    )
    version = await repo.add_version(
        aop_id=aop_row.id,
        source_md=payload.source_md,
        compiled_plan=aop.model_dump(),
        status="draft" if compile_errors else ("deployed" if payload.deploy else "ready"),
    )
    if payload.deploy and not compile_errors:
        await repo.set_current_version(aop_row.id, version.id)

    return AOPCreateResponse(
        aop_id=aop_row.id,
        version_id=version.id,
        version_number=version.version_number,
        status=version.status,
        compile_errors=compile_errors,
    )


class RunAOPRequest(BaseModel):
    aop_name: str
    case_id: str
    version_number: int | None = None  # default: current_version_id
    granted_scopes: list[str] | None = None


class RunAOPStarted(BaseModel):
    workflow_id: str
    run_id: UUID  # cogency aop_run.id (deep-linkable at /runs/{run_id})
    temporal_run_id: str  # Temporal's internal run id (for ops debugging only)
    aop_version_id: UUID


@router.post("/v1/aop_runs", response_model=RunAOPStarted, status_code=202)
async def trigger_run(
    payload: RunAOPRequest,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
    temporal: TemporalClient | None = Depends(temporal_client),
) -> RunAOPStarted:
    if temporal is None:
        raise HTTPException(503, "temporal unavailable")

    repo = AOPRepository(session)
    aop = await repo.get_by_name(settings.cogency_dev_tenant_id, payload.aop_name)
    if aop is None:
        raise HTTPException(404, f"AOP '{payload.aop_name}' not found")

    if payload.version_number is not None:
        stmt = select(AOPVersion).where(
            AOPVersion.aop_id == aop.id,
            AOPVersion.version_number == payload.version_number,
        )
        version = (await session.execute(stmt)).scalar_one_or_none()
    elif aop.current_version_id is not None:
        version = await session.get(AOPVersion, aop.current_version_id)
    else:
        version = await repo.latest_version(aop.id)

    if version is None:
        raise HTTPException(400, "AOP has no usable version; deploy a version first")

    # Pre-create the cogency aop_run row so we can return its id immediately.
    # The workflow activity adopts it (looks up by run_id and transitions to
    # status="running"), avoiding a race between API response and DB insert.
    run_repo = AOPRunRepository(session)
    run = await run_repo.create(
        tenant_id=settings.cogency_dev_tenant_id,
        aop_version_id=version.id,
        case_id=payload.case_id,
        trace_id="",  # filled by the activity
        status="pending",
    )

    workflow_id = f"aop-run-{aop.name}-{payload.case_id}-{run.id}"
    handle = await temporal.start_workflow(
        "RunAOPWorkflow",
        RunAOPInput(
            tenant_id=settings.cogency_dev_tenant_id,
            aop_version_id=version.id,
            case_id=payload.case_id,
            run_id=run.id,
            granted_scopes=payload.granted_scopes
            or [
                "case.read",
                "case.update",
                "contact.read",
                "refund.propose",
            ],
        ),
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    return RunAOPStarted(
        workflow_id=workflow_id,
        run_id=run.id,
        temporal_run_id=handle.first_execution_run_id or "",
        aop_version_id=version.id,
    )


class AOPRunListItem(BaseModel):
    id: UUID
    case_id: str
    aop_version_id: UUID
    aop_name: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    cost_usd: float
    token_in: int
    token_out: int


class AOPRunListResponse(BaseModel):
    items: list[AOPRunListItem]
    total: int


@router.get("/v1/aop_runs", response_model=AOPRunListResponse)
async def list_runs(
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
    status: str | None = None,
    case_id: str | None = None,
    aop_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AOPRunListResponse:
    base = (
        select(AOPRun, AOP.name)
        .join(AOPVersion, AOPVersion.id == AOPRun.aop_version_id)
        .join(AOP, AOP.id == AOPVersion.aop_id)
        .where(AOPRun.tenant_id == settings.cogency_dev_tenant_id)
    )
    if status:
        base = base.where(AOPRun.status == status)
    if case_id:
        base = base.where(AOPRun.case_id == case_id)
    if aop_name:
        base = base.where(AOP.name == aop_name)

    from sqlalchemy import func as _func

    total = (
        await session.execute(_func.count().select().select_from(base.subquery()))
    ).scalar_one()

    stmt = base.order_by(desc(AOPRun.started_at)).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).all()

    return AOPRunListResponse(
        items=[
            AOPRunListItem(
                id=run.id,
                case_id=run.case_id,
                aop_version_id=run.aop_version_id,
                aop_name=name,
                status=run.status,
                started_at=run.started_at,
                ended_at=run.ended_at,
                cost_usd=float(run.cost_usd or 0),
                token_in=run.token_in or 0,
                token_out=run.token_out or 0,
            )
            for run, name in rows
        ],
        total=total,
    )


@router.get("/v1/aop_runs/{run_id}", response_model=AOPRunSummary)
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(db_session),
) -> AOPRunSummary:
    repo = AOPRunRepository(session)
    run = await repo.get(run_id)
    if run is None:
        raise HTTPException(404, "aop_run not found")
    steps = await repo.steps(run_id)
    return AOPRunSummary(
        id=run.id,
        aop_version_id=run.aop_version_id,
        case_id=run.case_id,
        status=run.status,
        started_at=run.started_at,
        ended_at=run.ended_at,
        cost_usd=float(run.cost_usd or 0),
        token_in=run.token_in or 0,
        token_out=run.token_out or 0,
        trace_id=run.trace_id,
        steps=[
            {
                "step_index": s.step_index,
                "tool_name": s.tool_name,
                "input": s.input,
                "output": s.output,
                "status": s.status,
                "latency_ms": s.latency_ms,
                "error": s.error,
            }
            for s in steps
        ],
    )
