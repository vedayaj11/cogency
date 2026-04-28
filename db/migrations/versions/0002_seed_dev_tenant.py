"""Seed a deterministic dev tenant so local sync workflows have a valid org_id FK.

Idempotent — uses ON CONFLICT DO NOTHING.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEV_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO cogency.tenants (id, name, plan)
        VALUES ('{DEV_TENANT_ID}', 'cogency-dev', 'trial')
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM cogency.tenants WHERE id = '{DEV_TENANT_ID}'")
