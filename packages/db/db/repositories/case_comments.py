"""Repository for sf.case_comment mirror table."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.sf import SfCaseComment
from db.repositories._base import (
    MirrorUpsertRepository,
    _modstamp_or_now,
    _split_custom_fields,
    parse_sf_bool,
    parse_sf_datetime,
)


STOCK_FIELDS = {
    "Id",
    "ParentId",
    "CommentBody",
    "IsPublished",
    "CreatedById",
    "CreatedDate",
    "SystemModstamp",
    "IsDeleted",
}


def map_case_comment_row(org_id: UUID, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "org_id": org_id,
        "id": row["Id"],
        "parent_id": row.get("ParentId"),
        "comment_body": row.get("CommentBody"),
        "is_published": parse_sf_bool(row.get("IsPublished", "false")),
        "created_by_id": row.get("CreatedById"),
        "created_date": parse_sf_datetime(row.get("CreatedDate")),
        "custom_fields": _split_custom_fields(row, STOCK_FIELDS),
        "system_modstamp": _modstamp_or_now(row),
        "is_deleted": parse_sf_bool(row.get("IsDeleted", "false")),
    }


class CaseCommentRepository(MirrorUpsertRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SfCaseComment, map_case_comment_row)
