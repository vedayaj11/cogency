"""Golden datasets + eval run endpoints (PRD §6.6, §10.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient

from db.models.aop import AOP, AOPVersion
from db.models.eval import EvalResult, EvalRun, GoldenCase, GoldenDataset
from schemas import EvalRunInput

from app.config import Settings
from app.deps import db_session, settings_dep, temporal_client

router = APIRouter()


# ---------- datasets ----------

class GoldenDatasetCreate(BaseModel):
    name: str
    description: str | None = None
    aop_name: str | None = None


class GoldenDatasetItem(BaseModel):
    id: UUID
    name: str
    description: str | None
    aop_name: str | None
    cases_count: int
    created_at: datetime


class GoldenDatasetListResponse(BaseModel):
    items: list[GoldenDatasetItem]


@router.post("/v1/golden_datasets", response_model=GoldenDatasetItem)
async def create_dataset(
    payload: GoldenDatasetCreate,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> GoldenDatasetItem:
    existing = (
        await session.execute(
            select(GoldenDataset).where(
                GoldenDataset.tenant_id == settings.cogency_dev_tenant_id,
                GoldenDataset.name == payload.name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return GoldenDatasetItem(
            id=existing.id,
            name=existing.name,
            description=existing.description,
            aop_name=existing.aop_name,
            cases_count=0,
            created_at=existing.created_at,
        )
    ds = GoldenDataset(
        tenant_id=settings.cogency_dev_tenant_id,
        name=payload.name,
        description=payload.description,
        aop_name=payload.aop_name,
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return GoldenDatasetItem(
        id=ds.id,
        name=ds.name,
        description=ds.description,
        aop_name=ds.aop_name,
        cases_count=0,
        created_at=ds.created_at,
    )


@router.get("/v1/golden_datasets", response_model=GoldenDatasetListResponse)
async def list_datasets(
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> GoldenDatasetListResponse:
    from sqlalchemy import func as _func

    rows = list(
        (
            await session.execute(
                select(GoldenDataset)
                .where(GoldenDataset.tenant_id == settings.cogency_dev_tenant_id)
                .order_by(desc(GoldenDataset.created_at))
            )
        )
        .scalars()
        .all()
    )
    counts: dict[UUID, int] = {}
    if rows:
        count_rows = (
            await session.execute(
                select(GoldenCase.dataset_id, _func.count())
                .where(GoldenCase.dataset_id.in_([r.id for r in rows]))
                .group_by(GoldenCase.dataset_id)
            )
        ).all()
        counts = {a: b for a, b in count_rows}

    return GoldenDatasetListResponse(
        items=[
            GoldenDatasetItem(
                id=r.id,
                name=r.name,
                description=r.description,
                aop_name=r.aop_name,
                cases_count=counts.get(r.id, 0),
                created_at=r.created_at,
            )
            for r in rows
        ]
    )


# ---------- cases ----------

class GoldenCaseCreate(BaseModel):
    input_payload: dict[str, Any]
    expected_outcome: dict[str, Any]
    rubric: dict[str, str] | None = None
    tags: list[str] = []


class GoldenCaseItem(BaseModel):
    id: UUID
    dataset_id: UUID
    input_payload: dict[str, Any]
    expected_outcome: dict[str, Any]
    rubric: dict[str, Any] | None
    tags: list[str]
    created_at: datetime


@router.post("/v1/golden_datasets/{dataset_id}/cases", response_model=GoldenCaseItem)
async def add_case(
    dataset_id: UUID,
    payload: GoldenCaseCreate,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> GoldenCaseItem:
    ds = await session.get(GoldenDataset, dataset_id)
    if ds is None or ds.tenant_id != settings.cogency_dev_tenant_id:
        raise HTTPException(404, "dataset not found")
    gc = GoldenCase(
        dataset_id=dataset_id,
        input_payload=payload.input_payload,
        expected_outcome=payload.expected_outcome,
        rubric=payload.rubric,
        tags=payload.tags,
    )
    session.add(gc)
    await session.commit()
    await session.refresh(gc)
    return GoldenCaseItem(
        id=gc.id,
        dataset_id=gc.dataset_id,
        input_payload=gc.input_payload,
        expected_outcome=gc.expected_outcome,
        rubric=gc.rubric,
        tags=list(gc.tags or []),
        created_at=gc.created_at,
    )


# ---------- eval runs ----------

class EvalRunRequest(BaseModel):
    aop_name: str
    aop_version_number: int | None = None  # default: current version
    dataset_id: UUID
    pass_threshold: float = Field(default=0.85, ge=0.0, le=1.0)


class EvalRunStarted(BaseModel):
    workflow_id: str
    eval_run_id: UUID
    aop_version_id: UUID


@router.post("/v1/eval_runs", response_model=EvalRunStarted, status_code=202)
async def trigger_eval(
    payload: EvalRunRequest,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
    temporal: TemporalClient | None = Depends(temporal_client),
) -> EvalRunStarted:
    if temporal is None:
        raise HTTPException(503, "temporal unavailable")

    # Resolve AOP + version.
    aop = (
        await session.execute(
            select(AOP).where(
                AOP.tenant_id == settings.cogency_dev_tenant_id,
                AOP.name == payload.aop_name,
            )
        )
    ).scalar_one_or_none()
    if aop is None:
        raise HTTPException(404, f"AOP '{payload.aop_name}' not found")
    if payload.aop_version_number is not None:
        version = (
            await session.execute(
                select(AOPVersion).where(
                    AOPVersion.aop_id == aop.id,
                    AOPVersion.version_number == payload.aop_version_number,
                )
            )
        ).scalar_one_or_none()
    else:
        version = await session.get(AOPVersion, aop.current_version_id) if aop.current_version_id else None
        if version is None:
            # latest
            version = (
                await session.execute(
                    select(AOPVersion)
                    .where(AOPVersion.aop_id == aop.id)
                    .order_by(desc(AOPVersion.version_number))
                    .limit(1)
                )
            ).scalar_one_or_none()
    if version is None:
        raise HTTPException(400, "AOP has no usable version")

    dataset = await session.get(GoldenDataset, payload.dataset_id)
    if dataset is None or dataset.tenant_id != settings.cogency_dev_tenant_id:
        raise HTTPException(404, "dataset not found")

    # Pre-create eval_run row so the response carries its id.
    eval_run = EvalRun(
        tenant_id=settings.cogency_dev_tenant_id,
        dataset_id=dataset.id,
        aop_version_id=version.id,
        status="pending",
    )
    session.add(eval_run)
    await session.commit()
    await session.refresh(eval_run)

    workflow_id = f"eval-run-{aop.name}-{version.version_number}-{eval_run.id}"
    await temporal.start_workflow(
        "RunEvalWorkflow",
        EvalRunInput(
            tenant_id=settings.cogency_dev_tenant_id,
            eval_run_id=eval_run.id,
            dataset_id=dataset.id,
            aop_version_id=version.id,
            pass_threshold=payload.pass_threshold,
        ),
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    return EvalRunStarted(
        workflow_id=workflow_id, eval_run_id=eval_run.id, aop_version_id=version.id
    )


# ---------- eval run reads ----------

class EvalRunListItem(BaseModel):
    id: UUID
    aop_version_id: UUID
    aop_name: str | None
    aop_version_number: int | None
    dataset_id: UUID
    dataset_name: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    cases_total: int
    cases_passed: int
    pass_rate: float | None
    aggregate_scores: dict[str, Any] | None
    cost_usd: float | None


class EvalRunListResponse(BaseModel):
    items: list[EvalRunListItem]


@router.get("/v1/eval_runs", response_model=EvalRunListResponse)
async def list_eval_runs(
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
    limit: int = 50,
) -> EvalRunListResponse:
    rows = (
        await session.execute(
            select(EvalRun, AOP.name, AOPVersion.version_number, GoldenDataset.name)
            .join(AOPVersion, AOPVersion.id == EvalRun.aop_version_id)
            .join(AOP, AOP.id == AOPVersion.aop_id)
            .join(GoldenDataset, GoldenDataset.id == EvalRun.dataset_id)
            .where(EvalRun.tenant_id == settings.cogency_dev_tenant_id)
            .order_by(desc(EvalRun.started_at))
            .limit(limit)
        )
    ).all()

    return EvalRunListResponse(
        items=[
            EvalRunListItem(
                id=r.id,
                aop_version_id=r.aop_version_id,
                aop_name=aop_name,
                aop_version_number=v_num,
                dataset_id=r.dataset_id,
                dataset_name=ds_name,
                status=r.status,
                started_at=r.started_at,
                ended_at=r.ended_at,
                cases_total=r.cases_total,
                cases_passed=r.cases_passed,
                pass_rate=r.pass_rate,
                aggregate_scores=r.aggregate_scores,
                cost_usd=float(r.cost_usd) if r.cost_usd else None,
            )
            for r, aop_name, v_num, ds_name in rows
        ]
    )


class EvalResultItem(BaseModel):
    id: UUID
    golden_case_id: UUID
    aop_run_id: UUID | None
    passed: bool
    scores: dict[str, Any]
    aggregate: float
    judge_reasoning: str | None
    execution_status: str | None


class EvalRunDetail(EvalRunListItem):
    judge_model: str | None
    results: list[EvalResultItem]


@router.get("/v1/eval_runs/{eval_run_id}", response_model=EvalRunDetail)
async def get_eval_run(
    eval_run_id: UUID,
    settings: Settings = Depends(settings_dep),
    session: AsyncSession = Depends(db_session),
) -> EvalRunDetail:
    row = (
        await session.execute(
            select(EvalRun, AOP.name, AOPVersion.version_number, GoldenDataset.name)
            .join(AOPVersion, AOPVersion.id == EvalRun.aop_version_id)
            .join(AOP, AOP.id == AOPVersion.aop_id)
            .join(GoldenDataset, GoldenDataset.id == EvalRun.dataset_id)
            .where(
                EvalRun.id == eval_run_id,
                EvalRun.tenant_id == settings.cogency_dev_tenant_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "eval_run not found")
    r, aop_name, v_num, ds_name = row

    results = list(
        (
            await session.execute(
                select(EvalResult)
                .where(EvalResult.eval_run_id == eval_run_id)
                .order_by(EvalResult.created_at)
            )
        )
        .scalars()
        .all()
    )

    return EvalRunDetail(
        id=r.id,
        aop_version_id=r.aop_version_id,
        aop_name=aop_name,
        aop_version_number=v_num,
        dataset_id=r.dataset_id,
        dataset_name=ds_name,
        status=r.status,
        started_at=r.started_at,
        ended_at=r.ended_at,
        cases_total=r.cases_total,
        cases_passed=r.cases_passed,
        pass_rate=r.pass_rate,
        aggregate_scores=r.aggregate_scores,
        cost_usd=float(r.cost_usd) if r.cost_usd else None,
        judge_model=r.judge_model,
        results=[
            EvalResultItem(
                id=res.id,
                golden_case_id=res.golden_case_id,
                aop_run_id=res.aop_run_id,
                passed=res.passed,
                scores=res.scores,
                aggregate=res.aggregate,
                judge_reasoning=res.judge_reasoning,
                execution_status=res.execution_status,
            )
            for res in results
        ],
    )
