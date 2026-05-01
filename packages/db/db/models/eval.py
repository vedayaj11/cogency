"""ORM models for cogency.golden_datasets / golden_cases / eval_runs / eval_results.

Mirrors migration 0005. The `metadata`-attribute renaming trick is reused
for any JSONB columns whose Python name would shadow SQLAlchemy's
reserved attrs.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class GoldenDataset(Base):
    __tablename__ = "golden_datasets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_golden_datasets_tenant_name"),
        {"schema": "cogency"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    aop_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class GoldenCase(Base):
    __tablename__ = "golden_cases"
    __table_args__ = {"schema": "cogency"}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cogency.golden_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected_outcome: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rubric: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class EvalRun(Base):
    __tablename__ = "eval_runs"
    __table_args__ = {"schema": "cogency"}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cogency.golden_datasets.id"), nullable=False
    )
    aop_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cogency.aop_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    aggregate_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    pass_rate: Mapped[float | None] = mapped_column(Float)
    cases_total: Mapped[int] = mapped_column(Integer, default=0)
    cases_passed: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    judge_model: Mapped[str | None] = mapped_column(Text)
    baseline_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = (
        UniqueConstraint("eval_run_id", "golden_case_id", name="uq_eval_results_run_case"),
        {"schema": "cogency"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    eval_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cogency.eval_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    golden_case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cogency.golden_cases.id"),
        nullable=False,
    )
    aop_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cogency.aop_runs.id")
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    aggregate: Mapped[float] = mapped_column(Float, nullable=False)
    judge_reasoning: Mapped[str | None] = mapped_column(Text)
    execution_status: Mapped[str | None] = mapped_column(Text)
    execution_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    judge_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    diff_vs_baseline: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
