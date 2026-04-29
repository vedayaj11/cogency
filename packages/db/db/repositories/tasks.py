"""Repository for sf.task mirror table."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.sf import SfTask
from db.repositories._base import (
    MirrorUpsertRepository,
    _modstamp_or_now,
    _split_custom_fields,
    parse_sf_bool,
    parse_sf_date,
)


STOCK_FIELDS = {
    "Id",
    "WhatId",
    "WhoId",
    "OwnerId",
    "Subject",
    "Status",
    "Priority",
    "ActivityDate",
    "Description",
    "Type",
    "IsClosed",
    "SystemModstamp",
    "IsDeleted",
}


def map_task_row(org_id: UUID, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "org_id": org_id,
        "id": row["Id"],
        "what_id": row.get("WhatId"),
        "who_id": row.get("WhoId"),
        "owner_id": row.get("OwnerId"),
        "subject": row.get("Subject"),
        "status": row.get("Status"),
        "priority": row.get("Priority"),
        "activity_date": parse_sf_date(row.get("ActivityDate")),
        "description": row.get("Description"),
        "type": row.get("Type"),
        "is_closed": parse_sf_bool(row.get("IsClosed", "false")),
        "custom_fields": _split_custom_fields(row, STOCK_FIELDS),
        "system_modstamp": _modstamp_or_now(row),
        "is_deleted": parse_sf_bool(row.get("IsDeleted", "false")),
    }


class TaskRepository(MirrorUpsertRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SfTask, map_task_row)
