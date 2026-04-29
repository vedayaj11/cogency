"""Repositories for AOP authoring + run persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.aop import AOP, AgentInboxItem, AOPRun, AOPStep, AOPVersion


@dataclass
class AOPRepository:
    session: AsyncSession

    async def upsert_aop(
        self,
        *,
        tenant_id: UUID,
        name: str,
        description: str | None,
    ) -> AOP:
        existing = await self._get_by_name(tenant_id, name)
        if existing:
            if description is not None:
                existing.description = description
            await self.session.commit()
            return existing
        aop = AOP(tenant_id=tenant_id, name=name, description=description)
        self.session.add(aop)
        await self.session.commit()
        await self.session.refresh(aop)
        return aop

    async def _get_by_name(self, tenant_id: UUID, name: str) -> AOP | None:
        stmt = select(AOP).where(AOP.tenant_id == tenant_id, AOP.name == name)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_name(self, tenant_id: UUID, name: str) -> AOP | None:
        return await self._get_by_name(tenant_id, name)

    async def add_version(
        self,
        *,
        aop_id: UUID,
        source_md: str,
        compiled_plan: dict[str, Any],
        status: str = "draft",
        created_by: UUID | None = None,
    ) -> AOPVersion:
        next_version = (
            await self.session.execute(
                select(func.coalesce(func.max(AOPVersion.version_number), 0) + 1).where(
                    AOPVersion.aop_id == aop_id
                )
            )
        ).scalar_one()
        version = AOPVersion(
            aop_id=aop_id,
            version_number=next_version,
            source_md=source_md,
            compiled_plan=compiled_plan,
            status=status,
            created_by=created_by,
        )
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def set_current_version(self, aop_id: UUID, version_id: UUID) -> None:
        aop = await self.session.get(AOP, aop_id)
        if aop is None:
            raise KeyError(f"aop {aop_id} not found")
        aop.current_version_id = version_id
        await self.session.commit()

    async def latest_version(self, aop_id: UUID) -> AOPVersion | None:
        stmt = (
            select(AOPVersion)
            .where(AOPVersion.aop_id == aop_id)
            .order_by(desc(AOPVersion.version_number))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


@dataclass
class AOPRunRepository:
    session: AsyncSession

    async def create(
        self,
        *,
        tenant_id: UUID,
        aop_version_id: UUID,
        case_id: str,
        trace_id: str,
        status: str = "running",
    ) -> AOPRun:
        run = AOPRun(
            tenant_id=tenant_id,
            aop_version_id=aop_version_id,
            case_id=case_id,
            status=status,
            trace_id=trace_id,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def finalize(
        self,
        *,
        run_id: UUID,
        status: str,
        outcome: str | None,
        cost_usd: float,
        token_in: int,
        token_out: int,
        steps: list[dict[str, Any]],
    ) -> None:
        run = await self.session.get(AOPRun, run_id)
        if run is None:
            raise KeyError(f"aop_run {run_id} not found")
        run.status = status
        run.outcome = outcome
        run.cost_usd = Decimal(str(cost_usd))
        run.token_in = token_in
        run.token_out = token_out
        run.ended_at = datetime.now(UTC)

        for s in steps:
            self.session.add(
                AOPStep(
                    aop_run_id=run_id,
                    step_index=s["step_index"],
                    tool_name=s["tool_name"],
                    input=s.get("input"),
                    output=s.get("output"),
                    reasoning=s.get("reasoning"),
                    status=s["status"],
                    latency_ms=s.get("latency_ms"),
                    cost_usd=Decimal(str(s.get("cost_usd") or 0)),
                    error=s.get("error"),
                )
            )
        await self.session.commit()

    async def get(self, run_id: UUID) -> AOPRun | None:
        return await self.session.get(AOPRun, run_id)

    async def steps(self, run_id: UUID) -> list[AOPStep]:
        stmt = (
            select(AOPStep)
            .where(AOPStep.aop_run_id == run_id)
            .order_by(AOPStep.step_index)
        )
        return list((await self.session.execute(stmt)).scalars().all())


@dataclass
class InboxRepository:
    session: AsyncSession

    async def create(
        self,
        *,
        tenant_id: UUID,
        case_id: str,
        escalation_reason: str,
        recommended_action: dict[str, Any] | None = None,
        confidence: float | None = None,
    ) -> AgentInboxItem:
        item = AgentInboxItem(
            tenant_id=tenant_id,
            case_id=case_id,
            escalation_reason=escalation_reason,
            recommended_action=recommended_action,
            confidence=confidence,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item
