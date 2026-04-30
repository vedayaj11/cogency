"""Pub/Sub API gRPC consumer for Change Data Capture events.

PRD §7.2: subscribe to /data/CaseChangeEvent etc. with flow control,
ReplayId-based replay, ~1–3s end-to-end latency.

Implementation:
- gRPC `Subscribe` (bidirectional stream) with auth metadata (accesstoken,
  instanceurl, tenantid).
- Each FetchRequest pulls up to `batch_size` events; the consumer emits
  another FetchRequest after consuming a batch (flow control).
- Each `ConsumerEvent` carries an Avro-encoded payload + a `schema_id`. We
  fetch + cache the Avro schema via `GetSchema` and decode the payload
  with `fastavro.schemaless_reader`.
- Replay IDs are emitted to the caller as raw bytes; the caller persists
  them after each successful commit so a restart resumes from the last
  acknowledged position.
"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

try:
    import fastavro  # type: ignore[import-untyped]
    import grpc.aio
    from salesforce.pb import pubsub_api_pb2 as pb
    from salesforce.pb import pubsub_api_pb2_grpc as pb_grpc

    _GRPC_AVAILABLE = True
except ImportError:
    _GRPC_AVAILABLE = False

from salesforce.auth import AuthStrategy


@dataclass
class CDCEvent:
    """A decoded Change Data Capture event."""

    replay_id: bytes
    topic: str
    schema_id: str
    payload: dict[str, Any]

    @property
    def change_type(self) -> str:
        """CREATE / UPDATE / DELETE / UNDELETE / GAP_OVERFLOW / GAP_*."""
        header = self.payload.get("ChangeEventHeader") or {}
        return str(header.get("changeType", "UNKNOWN"))

    @property
    def record_ids(self) -> list[str]:
        header = self.payload.get("ChangeEventHeader") or {}
        ids = header.get("recordIds") or []
        return [str(x) for x in ids]

    @property
    def change_origin(self) -> str:
        header = self.payload.get("ChangeEventHeader") or {}
        return str(header.get("changeOrigin", ""))


@dataclass
class PubSubConsumer:
    auth: AuthStrategy
    endpoint: str = "api.pubsub.salesforce.com:7443"
    _schema_cache: dict[str, Any] = field(default_factory=dict, init=False)

    async def subscribe(
        self,
        topic: str,
        *,
        replay_id: bytes | None = None,
        batch_size: int = 100,
        tenant_id: str | None = None,
    ) -> AsyncIterator[CDCEvent]:
        """Yield decoded CDC events for `topic` (e.g. `/data/CaseChangeEvent`).

        If `replay_id` is provided, resumes from that position; otherwise
        starts at the tip (`ReplayPreset.LATEST`).
        """
        if not _GRPC_AVAILABLE:
            raise RuntimeError(
                "Pub/Sub consumer requires generated gRPC stubs + fastavro. "
                "Run scripts/gen_pubsub_proto.sh and ensure fastavro is installed."
            )

        token = await self.auth.access_token()
        # Salesforce Pub/Sub expects org_id as the `tenantid` metadata header.
        # The org_id is derivable from token.instance_url's lookup, but for
        # simplicity callers pass it explicitly when known.
        metadata = (
            ("accesstoken", token.access_token),
            ("instanceurl", token.instance_url),
            ("tenantid", tenant_id or ""),
        )

        # Reusable async generator for FetchRequests. The first request sets
        # the topic + replay preset; subsequent requests just refill the
        # flow-control window.
        request_q: asyncio.Queue[pb.FetchRequest] = asyncio.Queue()
        first = pb.FetchRequest(
            topic_name=topic,
            replay_preset=pb.ReplayPreset.CUSTOM if replay_id else pb.ReplayPreset.LATEST,
            replay_id=replay_id or b"",
            num_requested=batch_size,
        )
        await request_q.put(first)

        async def request_iter():
            while True:
                req = await request_q.get()
                yield req

        ssl_creds = grpc.ssl_channel_credentials()
        async with grpc.aio.secure_channel(self.endpoint, ssl_creds) as channel:
            stub = pb_grpc.PubSubStub(channel)
            response_stream = stub.Subscribe(request_iter(), metadata=metadata)

            async for response in response_stream:
                for event in response.events:
                    if not event.HasField("event"):
                        continue
                    schema = await self._get_schema(stub, metadata, event.event.schema_id)
                    payload = fastavro.schemaless_reader(
                        io.BytesIO(event.event.payload), schema
                    )
                    yield CDCEvent(
                        replay_id=event.replay_id,
                        topic=topic,
                        schema_id=event.event.schema_id,
                        payload=payload,
                    )

                # Refill the flow-control window after each batch.
                if response.pending_num_requested == 0:
                    await request_q.put(
                        pb.FetchRequest(num_requested=batch_size)
                    )

    async def _get_schema(
        self, stub, metadata: tuple[tuple[str, str], ...], schema_id: str
    ) -> Any:
        if schema_id in self._schema_cache:
            return self._schema_cache[schema_id]
        info = await stub.GetSchema(
            pb.SchemaRequest(schema_id=schema_id), metadata=metadata
        )
        parsed = fastavro.parse_schema(json.loads(info.schema_json))
        self._schema_cache[schema_id] = parsed
        return parsed
