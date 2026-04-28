"""Pub/Sub API gRPC consumer for Change Data Capture events.

PRD §7.2: subscribe to /data/CaseChangeEvent etc. with flow control,
ReplayId-based replay, and ~1–3s end-to-end latency.

Skeleton only — generate gRPC stubs from Salesforce's pubsub_api.proto and
implement Subscribe RPC with ReplayId persistence after COMMIT.
"""

from __future__ import annotations

from dataclasses import dataclass

from salesforce.auth import JWTBearerAuth


@dataclass
class PubSubConsumer:
    auth: JWTBearerAuth
    endpoint: str = "api.pubsub.salesforce.com:7443"

    async def subscribe(
        self,
        topic: str,
        *,
        replay_id: bytes | None = None,
        batch_size: int = 100,
    ):
        """Yield decoded CDC events for `topic` (e.g. /data/CaseChangeEvent)."""
        # TODO(salesforce-sync): build gRPC stub from pubsub_api.proto;
        # auth via tenantId + access token + instanceUrl headers;
        # decode Avro payloads using fetched schemas.
        raise NotImplementedError
        yield  # pragma: no cover  # noqa: RUF100
