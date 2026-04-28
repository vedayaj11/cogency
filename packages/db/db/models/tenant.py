from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "cogency"}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    salesforce_org_id: Mapped[str | None] = mapped_column(Text, unique=True)
    plan: Mapped[str] = mapped_column(Text, nullable=False, default="trial")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
