"""Repository for sf.email_message mirror table."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.sf import SfEmailMessage
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
    "FromAddress",
    "ToAddress",
    "CcAddress",
    "BccAddress",
    "Subject",
    "TextBody",
    "HtmlBody",
    "Status",
    "Incoming",
    "MessageDate",
    "SystemModstamp",
    "IsDeleted",
}


def map_email_row(org_id: UUID, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "org_id": org_id,
        "id": row["Id"],
        "parent_id": row.get("ParentId"),
        "from_address": row.get("FromAddress"),
        "to_address": row.get("ToAddress"),
        "cc_address": row.get("CcAddress"),
        "bcc_address": row.get("BccAddress"),
        "subject": row.get("Subject"),
        "text_body": row.get("TextBody"),
        "html_body": row.get("HtmlBody"),
        "status": row.get("Status"),
        "incoming": parse_sf_bool(row.get("Incoming", "false")),
        "message_date": parse_sf_datetime(row.get("MessageDate")),
        "custom_fields": _split_custom_fields(row, STOCK_FIELDS),
        "system_modstamp": _modstamp_or_now(row),
        "is_deleted": parse_sf_bool(row.get("IsDeleted", "false")),
    }


class EmailMessageRepository(MirrorUpsertRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SfEmailMessage, map_email_row)
