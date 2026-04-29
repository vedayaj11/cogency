"""Repository for sf.knowledge_article_version mirror table.

Schema is in place for milestone 6; population (RAG ingest, embedding) lands
in milestone 7. Reads are exposed as tools today so the agent can search
existing KBs once they're populated.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.sf import SfKnowledgeArticleVersion
from db.repositories._base import (
    MirrorUpsertRepository,
    _modstamp_or_now,
    _split_custom_fields,
    parse_sf_bool,
)


STOCK_FIELDS = {
    "Id",
    "KnowledgeArticleId",
    "Title",
    "Summary",
    "UrlName",
    "PublishStatus",
    "ArticleType",
    "Body",
    "Language",
    "SystemModstamp",
    "IsDeleted",
}


def map_kav_row(org_id: UUID, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "org_id": org_id,
        "id": row["Id"],
        "knowledge_article_id": row.get("KnowledgeArticleId"),
        "title": row.get("Title"),
        "summary": row.get("Summary"),
        "url_name": row.get("UrlName"),
        "publish_status": row.get("PublishStatus"),
        "article_type": row.get("ArticleType"),
        "body": row.get("Body"),
        "language": row.get("Language"),
        "custom_fields": _split_custom_fields(row, STOCK_FIELDS),
        "system_modstamp": _modstamp_or_now(row),
        "is_deleted": parse_sf_bool(row.get("IsDeleted", "false")),
    }


class KnowledgeRepository(MirrorUpsertRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SfKnowledgeArticleVersion, map_kav_row)
