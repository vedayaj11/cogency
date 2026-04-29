"""Base helper for sf.* mirror upsert repositories.

PRD §7.5: ON CONFLICT DO UPDATE WHERE EXCLUDED.system_modstamp >
sf.<table>.system_modstamp — out-of-order events never clobber newer data.

Each per-sobject repository provides a `map_row(org_id, raw)` mapper and the
ORM model class; the base handles batched upsert, custom_fields routing, and
the system_modstamp guard.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


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


def parse_sf_date(value: str | None):
    """Parse a Salesforce date (YYYY-MM-DD) into a datetime.date."""
    if value is None or value == "":
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_sf_bool(value: Any) -> bool:
    return str(value).lower() in {"true", "1", "yes"}


class MirrorUpsertRepository:
    """Generic batched upserter with system_modstamp guard.

    Subclass per sobject and call super().__init__ with the ORM model + row
    mapper.
    """

    def __init__(
        self,
        session: AsyncSession,
        model: type,
        map_row: Callable[[UUID, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.session = session
        self.model = model
        self.map_row = map_row

    async def upsert_many(
        self,
        org_id: UUID,
        rows: Iterable[dict[str, Any]],
        *,
        batch_size: int = 500,
    ) -> int:
        applied = 0
        batch: list[dict[str, Any]] = []
        for raw in rows:
            batch.append(self.map_row(org_id, raw))
            if len(batch) >= batch_size:
                applied += await self._flush(batch)
                batch = []
        if batch:
            applied += await self._flush(batch)
        return applied

    async def _flush(self, rows: list[dict[str, Any]]) -> int:
        stmt = insert(self.model).values(rows)
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in self.model.__table__.columns
            if c.name not in {"org_id", "id"}
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["org_id", "id"],
            set_=update_cols,
            where=self.model.system_modstamp < stmt.excluded.system_modstamp,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def count(self, org_id: UUID) -> int:
        stmt = select(self.model).where(self.model.org_id == org_id)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())


def _split_custom_fields(
    row: dict[str, Any], stock_fields: set[str]
) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in stock_fields}


def _modstamp_or_now(row: dict[str, Any]) -> datetime:
    return parse_sf_datetime(row.get("SystemModstamp")) or datetime.now(UTC)


__all__ = [
    "MirrorUpsertRepository",
    "parse_sf_datetime",
    "parse_sf_date",
    "parse_sf_bool",
    "_split_custom_fields",
    "_modstamp_or_now",
]
