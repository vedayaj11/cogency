"""Repository for cogency.sf_sync_state — watermarks + replay ids."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.sf import SfSyncState


@dataclass
class SyncStateRepository:
    session: AsyncSession

    async def get(
        self, org_id: UUID, sobject: str, channel: str
    ) -> SfSyncState | None:
        stmt = select(SfSyncState).where(
            SfSyncState.org_id == org_id,
            SfSyncState.sobject == sobject,
            SfSyncState.channel == channel,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        org_id: UUID,
        sobject: str,
        channel: str,
        watermark_ts: datetime | None = None,
        cdc_replay_id: bytes | None = None,
        last_status: str | None = None,
    ) -> None:
        payload = {
            "org_id": org_id,
            "sobject": sobject,
            "channel": channel,
            "watermark_ts": watermark_ts,
            "cdc_replay_id": cdc_replay_id,
            "last_run_at": datetime.now(UTC),
            "last_status": last_status,
        }
        stmt = insert(SfSyncState).values(payload)
        update_cols = {
            k: stmt.excluded[k]
            for k in ("watermark_ts", "cdc_replay_id", "last_run_at", "last_status")
            if payload[k] is not None or k in {"last_run_at", "last_status"}
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["org_id", "sobject", "channel"],
            set_=update_cols,
        )
        await self.session.execute(stmt)
        await self.session.commit()
