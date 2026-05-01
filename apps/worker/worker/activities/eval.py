"""Eval runner activity.

Runs an AOP version against every golden_case in a dataset, judges each
trace via the cross-family LLM-judge, and writes per-case eval_results
plus aggregate eval_run stats.

We do everything in one activity for simplicity. Each golden case is a
sub-step (heartbeats per case so Temporal sees progress); the activity
restarts on worker crashes — re-running is idempotent because the
eval_run row was pre-created by the API and we re-write eval_results via
ON CONFLICT.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from temporalio import activity

from agents import AOPExecutor, LLMClient
from aop import AOP
from db import (
    AOPRunRepository,
    AOPVersion,
    EvalResult,
    EvalRun,
    GoldenCase,
    GoldenDataset,
    async_session,
)
from evals import judge_run
from schemas import EvalRunInput, EvalRunResult
from tools import ToolContext, build_default_registry

from worker.config import get_settings


@activity.defn
async def execute_eval_run(payload: EvalRunInput) -> EvalRunResult:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    # Forward keys to os.environ so analyze.py and the judge's lazy clients
    # can read them.
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    os.environ.setdefault("OPENAI_DEFAULT_MODEL", settings.openai_default_model)
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

    llm = LLMClient(api_key=settings.openai_api_key, model=settings.openai_default_model)
    registry = build_default_registry()
    executor = AOPExecutor(llm=llm, registry=registry)

    # Load AOP, dataset, and cases up front.
    async with async_session(settings.database_url) as session:
        version = await session.get(AOPVersion, payload.aop_version_id)
        if version is None:
            raise RuntimeError(f"aop_version {payload.aop_version_id} not found")
        aop = AOP.model_validate(version.compiled_plan)

        dataset = await session.get(GoldenDataset, payload.dataset_id)
        if dataset is None:
            raise RuntimeError(f"golden_dataset {payload.dataset_id} not found")
        if dataset.tenant_id != payload.tenant_id:
            raise RuntimeError("dataset / tenant mismatch")

        cases = list(
            (
                await session.execute(
                    select(GoldenCase)
                    .where(GoldenCase.dataset_id == payload.dataset_id)
                    .order_by(GoldenCase.created_at)
                )
            )
            .scalars()
            .all()
        )

        # Mark eval_run as running.
        eval_run = await session.get(EvalRun, payload.eval_run_id)
        if eval_run is None:
            raise RuntimeError(f"eval_run {payload.eval_run_id} not pre-created")
        eval_run.status = "running"
        await session.commit()

    activity.logger.info(
        "eval.start",
        extra={
            "eval_run_id": str(payload.eval_run_id),
            "dataset": dataset.name,
            "cases": len(cases),
        },
    )

    cases_passed = 0
    cost_total = 0.0
    sum_tc = sum_pa = sum_tn = sum_ca = 0.0

    for i, gc in enumerate(cases):
        activity.heartbeat(f"eval case {i + 1}/{len(cases)}")

        # 1. Run the AOP against the golden case context.
        async with async_session(settings.database_url) as run_session:
            run_repo = AOPRunRepository(run_session)
            aop_run_row = await run_repo.create(
                tenant_id=payload.tenant_id,
                aop_version_id=payload.aop_version_id,
                case_id=str(gc.input_payload.get("case_id") or f"eval-{gc.id.hex[:8]}"),
                trace_id="",
                status="pending",
            )

        trace_id = str(uuid4())
        # Salesforce client not needed in eval mode (write-back tools will
        # fail with "no SF client"; that's fine — the trace just shows the
        # failure and the judge can score it appropriately).
        ctx_session_cm = async_session(settings.database_url)
        ctx_session = await ctx_session_cm.__aenter__()
        try:
            ctx = ToolContext(
                tenant_id=payload.tenant_id,
                case_id=aop_run_row.case_id,
                session=ctx_session,
                sf_client=None,
            )
            outcome = await executor.run(
                aop=aop,
                case_context=dict(gc.input_payload),
                tool_context=ctx,
                granted_scopes=[
                    "case.read",
                    "case.update",
                    "case.create",
                    "contact.read",
                    "account.read",
                    "email.draft",
                    "email.send",
                    "task.create",
                    "refund.propose",
                    "knowledge.read",
                ],
                aop_version_id=str(payload.aop_version_id),
                case_id=aop_run_row.case_id,
                trace_id=trace_id,
            )
        finally:
            await ctx_session_cm.__aexit__(None, None, None)

        # Persist the aop_run trace.
        async with async_session(settings.database_url) as fin_session:
            run_repo = AOPRunRepository(fin_session)
            await run_repo.finalize(
                run_id=aop_run_row.id,
                status=outcome.status,
                outcome=None,
                cost_usd=outcome.cost_usd,
                token_in=outcome.token_in,
                token_out=outcome.token_out,
                steps=[s.model_dump() for s in outcome.steps],
            )

        # 2. Judge the trace.
        final_message = ""
        for s in outcome.steps:
            if s.tool_name == "(final_message)" and isinstance(s.output, dict):
                final_message = str(s.output.get("text", ""))
        score = await judge_run(
            aop_name=aop.name,
            aop_description=aop.description,
            aop_body=aop.body,
            input_payload=dict(gc.input_payload),
            expected_outcome=dict(gc.expected_outcome),
            rubric=gc.rubric,
            status=outcome.status,
            final_message=final_message,
            steps=[s.model_dump() for s in outcome.steps],
            pass_threshold=payload.pass_threshold,
        )

        if score.passed:
            cases_passed += 1
        cost_total += outcome.cost_usd + score.judge_cost_usd
        sum_tc += score.task_completion
        sum_pa += score.policy_adherence
        sum_tn += score.tone
        sum_ca += score.citation_accuracy

        # 3. Persist eval_result.
        async with async_session(settings.database_url) as res_session:
            stmt = pg_insert(EvalResult.__table__).values(
                {
                    "eval_run_id": payload.eval_run_id,
                    "golden_case_id": gc.id,
                    "aop_run_id": aop_run_row.id,
                    "passed": score.passed,
                    "scores": {
                        "task_completion": score.task_completion,
                        "policy_adherence": score.policy_adherence,
                        "tone": score.tone,
                        "citation_accuracy": score.citation_accuracy,
                    },
                    "aggregate": score.aggregate,
                    "judge_reasoning": score.reasoning,
                    "execution_status": outcome.status,
                    "execution_cost_usd": Decimal(str(outcome.cost_usd)),
                    "judge_cost_usd": Decimal(str(score.judge_cost_usd)),
                }
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["eval_run_id", "golden_case_id"],
                set_={
                    "aop_run_id": stmt.excluded.aop_run_id,
                    "passed": stmt.excluded.passed,
                    "scores": stmt.excluded.scores,
                    "aggregate": stmt.excluded.aggregate,
                    "judge_reasoning": stmt.excluded.judge_reasoning,
                    "execution_status": stmt.excluded.execution_status,
                    "execution_cost_usd": stmt.excluded.execution_cost_usd,
                    "judge_cost_usd": stmt.excluded.judge_cost_usd,
                },
            )
            await res_session.execute(stmt)
            await res_session.commit()

    n = max(len(cases), 1)
    aggregate_scores = {
        "task_completion": sum_tc / n,
        "policy_adherence": sum_pa / n,
        "tone": sum_tn / n,
        "citation_accuracy": sum_ca / n,
    }
    pass_rate = cases_passed / n

    async with async_session(settings.database_url) as session:
        eval_run = await session.get(EvalRun, payload.eval_run_id)
        if eval_run is None:
            raise RuntimeError("eval_run vanished")
        eval_run.status = "completed"
        eval_run.ended_at = datetime.now(UTC)
        eval_run.cases_total = len(cases)
        eval_run.cases_passed = cases_passed
        eval_run.pass_rate = pass_rate
        eval_run.aggregate_scores = aggregate_scores
        eval_run.cost_usd = Decimal(str(cost_total))
        await session.commit()

    return EvalRunResult(
        eval_run_id=payload.eval_run_id,
        cases_total=len(cases),
        cases_passed=cases_passed,
        pass_rate=pass_rate,
        aggregate_scores=aggregate_scores,
        cost_usd=cost_total,
    )
