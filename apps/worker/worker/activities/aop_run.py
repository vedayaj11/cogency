"""AOP run activity: builds context, runs the executor, persists the trace."""

from __future__ import annotations

import os
from uuid import uuid4

from sqlalchemy import select
from temporalio import activity

from agents import AOPExecutor, LLMClient
from aop import AOP
from db import (
    AOPRun,
    AOPRunRepository,
    AOPVersion,
    InboxRepository,
    async_session,
)
from db.models.sf import SfCase
from schemas import RunAOPInput, RunAOPResult
from tools import ToolContext, build_default_registry

from worker.config import get_settings
from worker.sf import build_salesforce_client


@activity.defn
async def execute_aop_run(payload: RunAOPInput) -> RunAOPResult:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    # Tools that bypass the executor's LLMClient (the analyze.py family) read
    # OPENAI_API_KEY from os.environ. Pydantic-settings loads it from .env
    # into Settings, but doesn't propagate to os.environ — so do it here.
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    os.environ.setdefault("OPENAI_DEFAULT_MODEL", settings.openai_default_model)

    llm = LLMClient(api_key=settings.openai_api_key, model=settings.openai_default_model)
    registry = build_default_registry()
    executor = AOPExecutor(llm=llm, registry=registry)

    # Salesforce client only needed for write-back tools; stays None until used.
    try:
        sf_client = build_salesforce_client(settings)
    except Exception as e:
        activity.logger.warning("aop.sf_client_unavailable", extra={"error": str(e)})
        sf_client = None

    trace_id = str(uuid4())

    async with async_session(settings.database_url) as session:
        version = await session.get(AOPVersion, payload.aop_version_id)
        if version is None:
            raise RuntimeError(f"aop_version {payload.aop_version_id} not found")
        aop = AOP.model_validate(version.compiled_plan)

        case = (
            await session.execute(
                select(SfCase).where(
                    SfCase.org_id == payload.tenant_id, SfCase.id == payload.case_id
                )
            )
        ).scalar_one_or_none()
        if case is None:
            raise RuntimeError(f"case {payload.case_id} not in mirror; backfill first")

        case_context = {
            "case_id": case.id,
            "case_number": case.case_number,
            "subject": case.subject,
            "description": case.description,
            "status": case.status,
            "priority": case.priority,
            "contact_id": case.contact_id,
            "account_id": case.account_id,
            "custom_fields": case.custom_fields or {},
        }

        run_repo = AOPRunRepository(session)
        if payload.run_id is not None:
            # API pre-created the row; adopt it and transition to running.
            run = await run_repo.get(payload.run_id)
            if run is None:
                raise RuntimeError(f"aop_run {payload.run_id} not found")
            run.status = "running"
            run.trace_id = trace_id
            await session.commit()
        else:
            run = await run_repo.create(
                tenant_id=payload.tenant_id,
                aop_version_id=payload.aop_version_id,
                case_id=payload.case_id,
                trace_id=trace_id,
            )

    # Run the executor outside the persistence session so each tool call gets
    # a fresh transaction and we don't hold a connection during LLM calls.
    async with async_session(settings.database_url) as exec_session:
        ctx = ToolContext(
            tenant_id=payload.tenant_id,
            case_id=payload.case_id,
            session=exec_session,
            sf_client=sf_client,
        )
        outcome = await executor.run(
            aop=aop,
            case_context=case_context,
            tool_context=ctx,
            granted_scopes=payload.granted_scopes,
            aop_version_id=str(payload.aop_version_id),
            case_id=payload.case_id,
            trace_id=trace_id,
        )

    # Persist final state.
    async with async_session(settings.database_url) as session:
        run_repo = AOPRunRepository(session)
        await run_repo.finalize(
            run_id=run.id,
            status=outcome.status,
            outcome=None,
            cost_usd=outcome.cost_usd,
            token_in=outcome.token_in,
            token_out=outcome.token_out,
            steps=[s.model_dump() for s in outcome.steps],
        )
        if outcome.status == "escalated_human":
            inbox = InboxRepository(session)
            last = outcome.steps[-1] if outcome.steps else None
            # Pre-call gates record `awaiting_approval=True` in the step's
            # output and the proposed call's args in the input. Surface that
            # cleanly so the inbox-approve endpoint can re-fire the action.
            proposed_action: dict | None = None
            if (
                last is not None
                and last.status == "halted_by_guardrail"
                and isinstance(last.output, dict)
                and last.output.get("awaiting_approval") is True
            ):
                proposed_action = {
                    "tool": last.tool_name,
                    "args": last.input,
                    "reason": last.error,
                }
            await inbox.create(
                tenant_id=payload.tenant_id,
                case_id=payload.case_id,
                escalation_reason=(last.error if last else None) or "guardrail_required_approval",
                recommended_action={
                    "trace_id": trace_id,
                    "proposed_action": proposed_action,
                    "last_step": last.model_dump() if last else None,
                },
                confidence=None,
            )

    return RunAOPResult(
        run_id=run.id,
        status=outcome.status,
        cost_usd=outcome.cost_usd,
        token_in=outcome.token_in,
        token_out=outcome.token_out,
        step_count=len(outcome.steps),
    )
