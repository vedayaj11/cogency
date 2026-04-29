"""Extend sf.* mirror with EmailMessage, CaseComment, Task, KnowledgeArticleVersion.

These tables unblock the milestone-6 tool catalog (read case history,
draft contextual replies, schedule follow-ups) and the CDC consumer's need
to upsert email + comment events as they stream in.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _mirror_columns() -> list[sa.Column]:
    """Common columns for every sf.* mirror table — keep in sync with the
    `_SfMirrorMixin` in packages/db/db/models/sf.py.
    """
    return [
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", sa.Text, nullable=False),
        sa.Column("custom_fields", postgresql.JSONB, server_default="{}"),
        sa.Column("system_modstamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("_sync_version", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("pending_sync", sa.Boolean, nullable=False, server_default="false"),
    ]


def upgrade() -> None:
    # ---- email_message ----
    op.create_table(
        "email_message",
        *_mirror_columns(),
        sa.Column("parent_id", sa.Text),  # SF Case Id
        sa.Column("from_address", sa.Text),
        sa.Column("to_address", sa.Text),
        sa.Column("cc_address", sa.Text),
        sa.Column("bcc_address", sa.Text),
        sa.Column("subject", sa.Text),
        sa.Column("text_body", sa.Text),
        sa.Column("html_body", sa.Text),
        sa.Column("status", sa.Text),
        sa.Column("incoming", sa.Boolean, server_default="false"),
        sa.Column("message_date", sa.TIMESTAMP(timezone=True)),
        sa.PrimaryKeyConstraint("org_id", "id"),
        schema="sf",
    )
    op.create_index(
        "ix_sf_email_parent",
        "email_message",
        ["org_id", "parent_id"],
        schema="sf",
    )
    op.create_index(
        "ix_sf_email_modstamp",
        "email_message",
        ["org_id", "system_modstamp"],
        schema="sf",
    )
    op.create_index(
        "ix_sf_email_custom_gin",
        "email_message",
        ["custom_fields"],
        postgresql_using="gin",
        schema="sf",
    )

    # ---- case_comment ----
    op.create_table(
        "case_comment",
        *_mirror_columns(),
        sa.Column("parent_id", sa.Text),  # SF Case Id
        sa.Column("comment_body", sa.Text),
        sa.Column("is_published", sa.Boolean, server_default="false"),
        sa.Column("created_by_id", sa.Text),
        sa.Column("created_date", sa.TIMESTAMP(timezone=True)),
        sa.PrimaryKeyConstraint("org_id", "id"),
        schema="sf",
    )
    op.create_index(
        "ix_sf_case_comment_parent",
        "case_comment",
        ["org_id", "parent_id"],
        schema="sf",
    )
    op.create_index(
        "ix_sf_case_comment_modstamp",
        "case_comment",
        ["org_id", "system_modstamp"],
        schema="sf",
    )
    op.create_index(
        "ix_sf_case_comment_custom_gin",
        "case_comment",
        ["custom_fields"],
        postgresql_using="gin",
        schema="sf",
    )

    # ---- task ----
    op.create_table(
        "task",
        *_mirror_columns(),
        sa.Column("what_id", sa.Text),  # related-to: usually Case Id
        sa.Column("who_id", sa.Text),  # who: contact/lead Id
        sa.Column("owner_id", sa.Text),
        sa.Column("subject", sa.Text),
        sa.Column("status", sa.Text),
        sa.Column("priority", sa.Text),
        sa.Column("activity_date", sa.Date),
        sa.Column("description", sa.Text),
        sa.Column("type", sa.Text),  # Call, Email, Other
        sa.Column("is_closed", sa.Boolean, server_default="false"),
        sa.PrimaryKeyConstraint("org_id", "id"),
        schema="sf",
    )
    op.create_index(
        "ix_sf_task_what",
        "task",
        ["org_id", "what_id"],
        schema="sf",
    )
    op.create_index(
        "ix_sf_task_owner_open",
        "task",
        ["org_id", "owner_id", "is_closed"],
        schema="sf",
    )
    op.create_index(
        "ix_sf_task_modstamp",
        "task",
        ["org_id", "system_modstamp"],
        schema="sf",
    )

    # ---- knowledge_article_version ----
    op.create_table(
        "knowledge_article_version",
        *_mirror_columns(),
        sa.Column("knowledge_article_id", sa.Text),
        sa.Column("title", sa.Text),
        sa.Column("summary", sa.Text),
        sa.Column("url_name", sa.Text),
        sa.Column("publish_status", sa.Text),  # Draft, Online, Archived
        sa.Column("article_type", sa.Text),
        sa.Column("body", sa.Text),
        sa.Column("language", sa.Text),
        sa.PrimaryKeyConstraint("org_id", "id"),
        schema="sf",
    )
    op.create_index(
        "ix_sf_kav_modstamp",
        "knowledge_article_version",
        ["org_id", "system_modstamp"],
        schema="sf",
    )
    op.create_index(
        "ix_sf_kav_publish_status",
        "knowledge_article_version",
        ["org_id", "publish_status"],
        schema="sf",
    )


def downgrade() -> None:
    for tbl in ["knowledge_article_version", "task", "case_comment", "email_message"]:
        op.drop_table(tbl, schema="sf")
