"""Repository for sf.case mirror table.

PRD §7.5: ON CONFLICT DO UPDATE WHERE EXCLUDED.system_modstamp >
sf.case.system_modstamp — out-of-order events never clobber newer data.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.sf import SfCase

# Salesforce returns ISO-8601 timestamps; ParquetSQL expects datetime.
# Bulk CSV emits e.g. "2025-04-28T10:31:42.000+0000".
_SF_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
)


def parse_sf_datetime(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    for fmt in _SF_DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognized SF datetime format: {value}")


# Stock fields we mirror; everything else routes to custom_fields JSONB.
STOCK_CASE_FIELDS = {
    "Id",
    "CaseNumber",
    "Subject",
    "Description",
    "Status",
    "Priority",
    "Origin",
    "ContactId",
    "AccountId",
    "OwnerId",
    "CreatedDate",
    "SystemModstamp",
    "IsDeleted",
}


def map_case_row(org_id: UUID, row: dict[str, Any]) -> dict[str, Any]:
    """Map a Salesforce Case CSV/JSON row to an sf.case insert payload."""
    custom = {k: v for k, v in row.items() if k not in STOCK_CASE_FIELDS}
    is_deleted = str(row.get("IsDeleted", "false")).lower() in {"true", "1"}
    return {
        "org_id": org_id,
        "id": row["Id"],
        "case_number": row.get("CaseNumber"),
        "subject": row.get("Subject"),
        "description": row.get("Description"),
        "status": row.get("Status"),
        "priority": row.get("Priority"),
        "origin": row.get("Origin"),
        "contact_id": row.get("ContactId"),
        "account_id": row.get("AccountId"),
        "owner_id": row.get("OwnerId"),
        "custom_fields": custom,
        "created_date": parse_sf_datetime(row.get("CreatedDate")),
        "system_modstamp": parse_sf_datetime(row.get("SystemModstamp"))
        or datetime.utcnow(),
        "is_deleted": is_deleted,
    }


@dataclass
class CaseRepository:
    session: AsyncSession

    async def upsert_many(
        self,
        org_id: UUID,
        rows: Iterable[dict[str, Any]],
        *,
        batch_size: int = 500,
    ) -> int:
        """Upsert with system_modstamp guard. Returns count applied."""
        applied = 0
        batch: list[dict[str, Any]] = []
        for raw in rows:
            batch.append(map_case_row(org_id, raw))
            if len(batch) >= batch_size:
                applied += await self._flush(batch)
                batch = []
        if batch:
            applied += await self._flush(batch)
        return applied

    async def _flush(self, rows: list[dict[str, Any]]) -> int:
        stmt = insert(SfCase).values(rows)
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in SfCase.__table__.columns
            if c.name not in {"org_id", "id"}
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["org_id", "id"],
            set_=update_cols,
            where=SfCase.system_modstamp < stmt.excluded.system_modstamp,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def count(self, org_id: UUID) -> int:
        stmt = select(SfCase).where(SfCase.org_id == org_id)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())
