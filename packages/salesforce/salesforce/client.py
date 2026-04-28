"""High-level Salesforce REST + Bulk client.

Holds an AuthStrategy and provides typed async methods for SOQL, Bulk 2.0
query jobs, and conditional REST writes. All methods honor the Sforce-Limit-Info
header to populate a per-instance rate-limit gauge.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from salesforce.auth import AuthStrategy

log = logging.getLogger("cogency.salesforce")


class SalesforceAPIError(Exception):
    def __init__(self, status: int, body: str, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(f"Salesforce API {status}: {body[:300]}")
        self.status = status
        self.body = body
        self.errors = errors or []


class ConflictError(SalesforceAPIError):
    """Raised on 412 Precondition Failed (If-Unmodified-Since conflict)."""


@dataclass
class RateLimitInfo:
    used: int = 0
    total: int = 0

    @property
    def percent_used(self) -> float:
        return (self.used / self.total * 100) if self.total else 0.0


@dataclass
class SalesforceClient:
    auth: AuthStrategy
    api_version: str = "62.0"
    timeout: float = 60.0
    rate_limit: RateLimitInfo = field(default_factory=RateLimitInfo)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | str | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        token = await self.auth.access_token()
        url = f"{token.instance_url}{path}" if path.startswith("/") else path
        merged_headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Accept": "application/json",
        }
        if headers:
            merged_headers.update(headers)
        if json_body is not None:
            merged_headers.setdefault("Content-Type", "application/json")

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(initial=1, max=30),
            retry=retry_if_exception_type((httpx.TransportError, httpx.ReadTimeout)),
            reraise=True,
        ):
            with attempt:
                client = httpx.AsyncClient(timeout=self.timeout)
                try:
                    resp = await client.request(
                        method,
                        url,
                        json=json_body,
                        params=params,
                        headers=merged_headers,
                        content=content,
                    )
                finally:
                    if not stream:
                        await client.aclose()
                self._update_rate_limit(resp)
                if resp.status_code == 412:
                    raise ConflictError(412, resp.text)
                if resp.status_code == 429 or resp.status_code >= 500:
                    retry_after = float(resp.headers.get("Retry-After", "1"))
                    await asyncio.sleep(retry_after)
                    raise httpx.TransportError(f"retryable status {resp.status_code}")
                if resp.status_code >= 400:
                    errors = None
                    try:
                        errors = resp.json()
                    except Exception:
                        pass
                    raise SalesforceAPIError(resp.status_code, resp.text, errors)
                return resp

        raise RuntimeError("unreachable")

    def _update_rate_limit(self, resp: httpx.Response) -> None:
        # Sforce-Limit-Info: api-usage=12345/15000000
        info = resp.headers.get("Sforce-Limit-Info")
        if not info:
            return
        for chunk in info.split(","):
            chunk = chunk.strip()
            if chunk.startswith("api-usage="):
                used_total = chunk.split("=", 1)[1]
                used, total = used_total.split("/", 1)
                self.rate_limit = RateLimitInfo(used=int(used), total=int(total))

    # ---------- REST query ----------

    async def query(self, soql: str) -> dict[str, Any]:
        resp = await self._request(
            "GET",
            f"/services/data/v{self.api_version}/query",
            params={"q": soql},
        )
        return resp.json()

    async def query_all(self, soql: str) -> AsyncIterator[dict[str, Any]]:
        """Stream every record from a SOQL query, following nextRecordsUrl."""
        resp = await self._request(
            "GET",
            f"/services/data/v{self.api_version}/query",
            params={"q": soql},
        )
        page = resp.json()
        for rec in page.get("records", []):
            yield rec
        while not page.get("done", True):
            next_url = page["nextRecordsUrl"]
            resp = await self._request("GET", next_url)
            page = resp.json()
            for rec in page.get("records", []):
                yield rec

    # ---------- REST writes ----------

    async def update_record(
        self,
        sobject: str,
        record_id: str,
        fields: dict[str, Any],
        *,
        if_unmodified_since: str | None = None,
    ) -> None:
        headers = {}
        if if_unmodified_since:
            headers["If-Unmodified-Since"] = if_unmodified_since
        await self._request(
            "PATCH",
            f"/services/data/v{self.api_version}/sobjects/{sobject}/{record_id}",
            json_body=fields,
            headers=headers,
        )

    async def composite_upsert(
        self,
        sobject: str,
        records: list[dict[str, Any]],
        *,
        external_id_field: str = "Id",
        all_or_none: bool = False,
    ) -> list[dict[str, Any]]:
        if len(records) > 200:
            raise ValueError("composite/sobjects accepts ≤200 records per call")
        body = {
            "allOrNone": all_or_none,
            "records": [{**r, "attributes": {"type": sobject}} for r in records],
        }
        resp = await self._request(
            "PATCH",
            f"/services/data/v{self.api_version}/composite/sobjects/{sobject}/{external_id_field}",
            json_body=body,
        )
        return resp.json()

    # ---------- Bulk 2.0 query ----------

    async def submit_query_job(
        self,
        soql: str,
        *,
        line_ending: str = "LF",
        column_delimiter: str = "COMMA",
    ) -> str:
        body = {
            "operation": "query",
            "query": soql,
            "contentType": "CSV",
            "lineEnding": line_ending,
            "columnDelimiter": column_delimiter,
        }
        resp = await self._request(
            "POST", f"/services/data/v{self.api_version}/jobs/query", json_body=body
        )
        return resp.json()["id"]

    async def get_query_job(self, job_id: str) -> dict[str, Any]:
        resp = await self._request(
            "GET", f"/services/data/v{self.api_version}/jobs/query/{job_id}"
        )
        return resp.json()

    async def wait_for_query_job(
        self,
        job_id: str,
        *,
        poll_interval: float = 5.0,
        timeout: float = 30 * 60,
    ) -> dict[str, Any]:
        elapsed = 0.0
        while elapsed < timeout:
            job = await self.get_query_job(job_id)
            state = job.get("state")
            log.info("bulk.poll", extra={"job_id": job_id, "state": state})
            if state == "JobComplete":
                return job
            if state in {"Failed", "Aborted"}:
                raise SalesforceAPIError(0, f"bulk job {state}: {job}")
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise SalesforceAPIError(0, f"bulk job timeout after {timeout}s")

    async def iter_query_results(
        self, job_id: str, *, max_records: int = 100_000
    ) -> AsyncIterator[bytes]:
        """Yield CSV result chunks, following Sforce-Locator pagination."""
        locator: str | None = None
        while True:
            params = {"maxRecords": max_records}
            if locator:
                params["locator"] = locator
            resp = await self._request(
                "GET",
                f"/services/data/v{self.api_version}/jobs/query/{job_id}/results",
                params=params,
                headers={"Accept": "text/csv"},
            )
            yield resp.content
            locator = resp.headers.get("Sforce-Locator")
            if not locator or locator == "null":
                break

    async def delete_query_job(self, job_id: str) -> None:
        await self._request(
            "DELETE", f"/services/data/v{self.api_version}/jobs/query/{job_id}"
        )
