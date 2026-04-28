"""Writer outbox: REST composite/sobjects PATCH with optimistic concurrency.

PRD §7.5: Salesforce-wins by default; PATCH with If-Unmodified-Since; on 412 →
DLQ with diff and "agent re-evaluate" trigger. Filter own writes from CDC echo
via ChangeEventHeader.changeOrigin.
"""

from __future__ import annotations

from dataclasses import dataclass

from salesforce.auth import JWTBearerAuth


@dataclass
class OutboxWriter:
    auth: JWTBearerAuth

    async def patch_record(
        self,
        sobject: str,
        record_id: str,
        fields: dict,
        *,
        if_unmodified_since: str | None = None,
    ) -> dict:
        """Single-record PATCH for conflict-sensitive writes."""
        # TODO(salesforce-sync): implement with conditional header + 412 handling
        raise NotImplementedError

    async def composite_upsert(
        self,
        sobject: str,
        records: list[dict],
        external_id_field: str = "Id",
    ) -> list[dict]:
        """Batch upsert via composite/sobjects (≤200 records/call)."""
        # TODO(salesforce-sync)
        raise NotImplementedError
