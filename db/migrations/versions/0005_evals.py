"""Eval & Observability schema (PRD §6.6, §9.2).

`golden_datasets` + `golden_cases` are the curated test sets — each
golden_case carries a synthetic case_context the AOP runs against, plus
an expected_outcome and a rubric. `eval_runs` track batch executions of an
AOP version against a dataset; `eval_results` record per-case rubric
scores from the LLM-judge.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "golden_datasets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("aop_name", sa.Text),  # optional: scope dataset to a single AOP
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_golden_datasets_tenant_name"),
        schema="cogency",
    )

    op.create_table(
        "golden_cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.golden_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The case context to feed the AOP — same shape as the runtime
        # case_context dict (subject, description, contact_id, ...). A
        # `case_id` field can be supplied for stable identity in the trace.
        sa.Column("input_payload", postgresql.JSONB, nullable=False),
        # Free-form description of the right answer for this case
        # (e.g. "agent should propose refund of $45 and add internal comment").
        sa.Column("expected_outcome", postgresql.JSONB, nullable=False),
        # Rubric criteria override — defaults applied at run time if NULL.
        sa.Column("rubric", postgresql.JSONB),
        sa.Column("tags", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="cogency",
    )
    op.create_index(
        "ix_golden_cases_dataset",
        "golden_cases",
        ["dataset_id"],
        schema="cogency",
    )

    op.create_table(
        "eval_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.golden_datasets.id"),
            nullable=False,
        ),
        sa.Column(
            "aop_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.aop_versions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text, nullable=False),  # pending|running|completed|failed
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("aggregate_scores", postgresql.JSONB),  # rubric averages
        sa.Column("pass_rate", sa.Float),  # 0..1
        sa.Column("cases_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cases_passed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 4)),
        sa.Column("judge_model", sa.Text),
        sa.Column("baseline_run_id", postgresql.UUID(as_uuid=True)),
        schema="cogency",
    )
    op.create_index(
        "ix_eval_runs_aop_version",
        "eval_runs",
        ["tenant_id", "aop_version_id"],
        schema="cogency",
    )

    op.create_table(
        "eval_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "eval_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.eval_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "golden_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.golden_cases.id"),
            nullable=False,
        ),
        # The aop_run.id that this eval_result corresponds to (so you can
        # click through to the live trace at /runs/{id}).
        sa.Column(
            "aop_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cogency.aop_runs.id"),
        ),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("scores", postgresql.JSONB, nullable=False),  # 4-dim rubric
        sa.Column("aggregate", sa.Float, nullable=False),
        sa.Column("judge_reasoning", sa.Text),
        sa.Column("execution_status", sa.Text),  # resolved|escalated|failed
        sa.Column("execution_cost_usd", sa.Numeric(10, 4)),
        sa.Column("judge_cost_usd", sa.Numeric(10, 4)),
        # Diff vs baseline run for the same golden_case (filled in only when
        # eval_runs.baseline_run_id is set).
        sa.Column("diff_vs_baseline", postgresql.JSONB),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "eval_run_id", "golden_case_id", name="uq_eval_results_run_case"
        ),
        schema="cogency",
    )


def downgrade() -> None:
    for tbl in ["eval_results", "eval_runs", "golden_cases", "golden_datasets"]:
        op.drop_table(tbl, schema="cogency")
