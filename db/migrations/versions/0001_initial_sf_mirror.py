"""Initial schema: sf.* mirror tables, sync state, cogency-native entities.

Implements the data model from PRD §7.7, §9.1, §9.2.

Revision ID: 0001
Revises:
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    has_vector = bool(
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name='vector'"))
        .scalar()
    )
    if has_vector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS sf")
    op.execute("CREATE SCHEMA IF NOT EXISTS cogency")

    # ---- tenancy & auth ----
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("salesforce_org_id", sa.Text, unique=True),
        sa.Column("plan", sa.Text, nullable=False, server_default="trial"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="cogency",
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),  # admin|cx_architect|senior_agent|agent
        sa.Column("persona_assignments", postgresql.JSONB, server_default="[]"),
        sa.Column("sso_connection_id", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email"),
        schema="cogency",
    )

    # ---- salesforce sync state ----
    op.create_table(
        "sf_sync_state",
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sobject", sa.Text, nullable=False),
        sa.Column("channel", sa.Text, nullable=False),  # bulk|cdc|getupdated
        sa.Column("watermark_ts", sa.TIMESTAMP(timezone=True)),
        sa.Column("cdc_replay_id", sa.LargeBinary),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_status", sa.Text),
        sa.PrimaryKeyConstraint("org_id", "sobject", "channel"),
        schema="cogency",
    )

    # ---- sf.* mirror (case is the hot path; others stubbed for §7.7 ----
    for table, extra_cols in [
        ("account", []),
        ("contact", [
            sa.Column("first_name", sa.Text),
            sa.Column("last_name", sa.Text),
            sa.Column("email", sa.Text),
            sa.Column("account_id", sa.Text),
        ]),
        ("user", [
            sa.Column("username", sa.Text),
            sa.Column("email", sa.Text),
        ]),
    ]:
        op.create_table(
            table,
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("id", sa.Text, nullable=False),  # SF 18-char
            sa.Column("name", sa.Text),
            *extra_cols,
            sa.Column("custom_fields", postgresql.JSONB, server_default="{}"),
            sa.Column("system_modstamp", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("_sync_version", sa.BigInteger, nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("pending_sync", sa.Boolean, nullable=False, server_default="false"),
            sa.PrimaryKeyConstraint("org_id", "id"),
            schema="sf",
        )
        op.create_index(
            f"ix_sf_{table}_modstamp", table, ["org_id", "system_modstamp"], schema="sf"
        )
        op.create_index(
            f"ix_sf_{table}_custom_gin", table, ["custom_fields"],
            postgresql_using="gin", schema="sf",
        )

    # case is hotter — give it more fields and an embedding column
    op.create_table(
        "case",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", sa.Text, nullable=False),
        sa.Column("case_number", sa.Text),
        sa.Column("subject", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.Text),
        sa.Column("priority", sa.Text),
        sa.Column("origin", sa.Text),
        sa.Column("contact_id", sa.Text),
        sa.Column("account_id", sa.Text),
        sa.Column("owner_id", sa.Text),
        sa.Column("custom_fields", postgresql.JSONB, server_default="{}"),
        sa.Column("embedding", sa.dialects.postgresql.ARRAY(sa.Float)),  # placeholder; switch to vector(1536) after pgvector load
        sa.Column("created_date", sa.TIMESTAMP(timezone=True)),
        sa.Column("system_modstamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("_sync_version", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("pending_sync", sa.Boolean, nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("org_id", "id"),
        schema="sf",
    )
    op.create_index("ix_sf_case_modstamp", "case", ["org_id", "system_modstamp"], schema="sf")
    op.create_index("ix_sf_case_contact", "case", ["org_id", "contact_id"], schema="sf")
    op.create_index("ix_sf_case_status", "case", ["org_id", "status"], schema="sf")
    op.create_index("ix_sf_case_custom_gin", "case", ["custom_fields"],
                    postgresql_using="gin", schema="sf")

    # promote embedding to pgvector when available; otherwise leave as float[]
    # (nothing reads or writes the column yet — RAG layer comes later).
    if has_vector:
        op.execute("ALTER TABLE sf.case DROP COLUMN embedding")
        op.execute("ALTER TABLE sf.case ADD COLUMN embedding vector(1536)")

    # ---- cogency-native: AOP engine, inbox, evals, audit ----
    op.create_table(
        "aops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name"),
        schema="cogency",
    )

    op.create_table(
        "aop_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("aop_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.aops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("source_md", sa.Text, nullable=False),
        sa.Column("compiled_plan", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("aop_id", "version_number"),
        schema="cogency",
    )

    op.create_table(
        "aop_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("aop_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.aop_versions.id"), nullable=False),
        sa.Column("case_id", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("outcome", sa.Text),
        sa.Column("cost_usd", sa.Numeric(10, 4)),
        sa.Column("token_in", sa.BigInteger),
        sa.Column("token_out", sa.BigInteger),
        sa.Column("trace_id", sa.Text),
        schema="cogency",
    )
    op.create_index("ix_aop_runs_case", "aop_runs", ["tenant_id", "case_id"], schema="cogency")

    op.create_table(
        "aop_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("aop_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.aop_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("input", postgresql.JSONB),
        sa.Column("output", postgresql.JSONB),
        sa.Column("reasoning", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(10, 4)),
        sa.Column("error", sa.Text),
        sa.UniqueConstraint("aop_run_id", "step_index"),
        schema="cogency",
    )

    op.create_table(
        "agent_inbox_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.Text, nullable=False),
        sa.Column("escalation_reason", sa.Text, nullable=False),
        sa.Column("recommended_action", postgresql.JSONB),
        sa.Column("confidence", sa.Float),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True)),
        sa.Column("sla_deadline", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="cogency",
    )
    op.create_index(
        "ix_inbox_status_sla",
        "agent_inbox_items",
        ["tenant_id", "status", "sla_deadline"],
        schema="cogency",
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_type", sa.Text, nullable=False),  # human|agent
        sa.Column("actor_id", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text),
        sa.Column("target_id", sa.Text),
        sa.Column("before", postgresql.JSONB),
        sa.Column("after", postgresql.JSONB),
        sa.Column("trace_id", sa.Text),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="cogency",
    )
    op.create_index(
        "ix_audit_tenant_time", "audit_events",
        ["tenant_id", "timestamp"], schema="cogency",
    )

    op.create_table(
        "tenant_budgets",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cogency.tenants.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("monthly_token_cap", sa.BigInteger),
        sa.Column("current_month_tokens", sa.BigInteger, server_default="0"),
        sa.Column("per_conversation_cap", sa.Integer, server_default="100000"),
        sa.Column("kill_switch_threshold", sa.Numeric(10, 4)),
        schema="cogency",
    )


def downgrade() -> None:
    for tbl in [
        "tenant_budgets", "audit_events", "agent_inbox_items",
        "aop_steps", "aop_runs", "aop_versions", "aops",
        "users", "tenants", "sf_sync_state",
    ]:
        op.drop_table(tbl, schema="cogency")
    for tbl in ["case", "contact", "account", "user"]:
        op.drop_table(tbl, schema="sf")
    op.execute("DROP SCHEMA IF EXISTS cogency")
    op.execute("DROP SCHEMA IF EXISTS sf")
