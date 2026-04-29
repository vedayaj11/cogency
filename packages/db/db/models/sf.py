"""ORM models for the sf.* mirror schema.

Mirrors the migration in db/migrations/versions/0001_initial_sf_mirror.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from datetime import date

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Date,
    LargeBinary,
    PrimaryKeyConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class _SfMirrorMixin:
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    id: Mapped[str] = mapped_column(Text, nullable=False)  # SF 18-char
    custom_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    system_modstamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    _sync_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pending_sync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SfAccount(Base, _SfMirrorMixin):
    __tablename__ = "account"
    __table_args__ = (PrimaryKeyConstraint("org_id", "id"), {"schema": "sf"})

    name: Mapped[str | None] = mapped_column(Text)


class SfContact(Base, _SfMirrorMixin):
    __tablename__ = "contact"
    __table_args__ = (PrimaryKeyConstraint("org_id", "id"), {"schema": "sf"})

    name: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[str | None] = mapped_column(Text)


class SfUser(Base, _SfMirrorMixin):
    __tablename__ = "user"
    __table_args__ = (PrimaryKeyConstraint("org_id", "id"), {"schema": "sf"})

    name: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)


class SfCase(Base, _SfMirrorMixin):
    __tablename__ = "case"
    __table_args__ = (PrimaryKeyConstraint("org_id", "id"), {"schema": "sf"})

    case_number: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str | None] = mapped_column(Text)
    contact_id: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(Text)
    created_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class SfEmailMessage(Base, _SfMirrorMixin):
    __tablename__ = "email_message"
    __table_args__ = (PrimaryKeyConstraint("org_id", "id"), {"schema": "sf"})

    parent_id: Mapped[str | None] = mapped_column(Text)  # SF Case Id
    from_address: Mapped[str | None] = mapped_column(Text)
    to_address: Mapped[str | None] = mapped_column(Text)
    cc_address: Mapped[str | None] = mapped_column(Text)
    bcc_address: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    text_body: Mapped[str | None] = mapped_column(Text)
    html_body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    incoming: Mapped[bool] = mapped_column(Boolean, default=False)
    message_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class SfCaseComment(Base, _SfMirrorMixin):
    __tablename__ = "case_comment"
    __table_args__ = (PrimaryKeyConstraint("org_id", "id"), {"schema": "sf"})

    parent_id: Mapped[str | None] = mapped_column(Text)  # SF Case Id
    comment_body: Mapped[str | None] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[str | None] = mapped_column(Text)
    created_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class SfTask(Base, _SfMirrorMixin):
    __tablename__ = "task"
    __table_args__ = (PrimaryKeyConstraint("org_id", "id"), {"schema": "sf"})

    what_id: Mapped[str | None] = mapped_column(Text)  # related-to (Case)
    who_id: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text)
    activity_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)


class SfKnowledgeArticleVersion(Base, _SfMirrorMixin):
    __tablename__ = "knowledge_article_version"
    __table_args__ = (PrimaryKeyConstraint("org_id", "id"), {"schema": "sf"})

    knowledge_article_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    url_name: Mapped[str | None] = mapped_column(Text)
    publish_status: Mapped[str | None] = mapped_column(Text)
    article_type: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)


class SfSyncState(Base):
    __tablename__ = "sf_sync_state"
    __table_args__ = (
        PrimaryKeyConstraint("org_id", "sobject", "channel"),
        {"schema": "cogency"},
    )

    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sobject: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)  # bulk|cdc|getupdated
    watermark_ts: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    cdc_replay_id: Mapped[bytes | None] = mapped_column(LargeBinary)
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_status: Mapped[str | None] = mapped_column(Text)
