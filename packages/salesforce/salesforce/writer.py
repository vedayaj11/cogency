"""Writer outbox: REST PATCH with optimistic concurrency and DLQ on conflict.

PRD §7.5: Salesforce-wins by default. PATCH with If-Unmodified-Since; on 412 →
DLQ with diff and "agent re-evaluate" trigger. Filter own writes from CDC echo
via ChangeEventHeader.changeOrigin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from salesforce.client import ConflictError, SalesforceClient


@dataclass
class WriteOutcome:
    record_id: str
    succeeded: bool
    conflict: bool = False
    error: str | None = None


@dataclass
class OutboxWriter:
    client: SalesforceClient

    async def patch_record(
        self,
        sobject: str,
        record_id: str,
        fields: dict[str, Any],
        *,
        if_unmodified_since: str | None = None,
    ) -> WriteOutcome:
        try:
            await self.client.update_record(
                sobject, record_id, fields, if_unmodified_since=if_unmodified_since
            )
            return WriteOutcome(record_id=record_id, succeeded=True)
        except ConflictError as e:
            return WriteOutcome(
                record_id=record_id, succeeded=False, conflict=True, error=str(e)
            )

    async def composite_upsert(
        self,
        sobject: str,
        records: list[dict[str, Any]],
        *,
        external_id_field: str = "Id",
    ) -> list[WriteOutcome]:
        results = await self.client.composite_upsert(
            sobject, records, external_id_field=external_id_field
        )
        outcomes = []
        for r in results:
            outcomes.append(
                WriteOutcome(
                    record_id=r.get("id", ""),
                    succeeded=r.get("success", False),
                    error=str(r.get("errors")) if not r.get("success") else None,
                )
            )
        return outcomes
