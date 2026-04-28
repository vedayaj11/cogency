"""Pub/Sub API gRPC consumer for Change Data Capture events.

PRD §7.2: subscribe to /data/CaseChangeEvent etc. with flow control,
ReplayId-based replay, ~1–3s end-to-end latency.

The gRPC stubs are generated from Salesforce's `pubsub_api.proto` — fetch and
generate via `scripts/gen_pubsub_proto.sh`. Until then `subscribe()` raises
NotImplementedError; the data flow + auth headers are documented inline so the
implementation lands cleanly when the stubs exist.

Implementation outline (when stubs are present):

    from salesforce.pb.pubsub_api_pb2 import FetchRequest
    from salesforce.pb.pubsub_api_pb2_grpc import PubSubStub

    channel = grpc.aio.secure_channel(endpoint, grpc.ssl_channel_credentials())
    stub = PubSubStub(channel)
    metadata = (
        ("accesstoken", token.access_token),
        ("instanceurl", token.instance_url),
        ("tenantid", org_id),
    )
    schema_cache: dict[str, fastavro.parsed_schema] = {}

    def request_iter():
        yield FetchRequest(topic_name=topic, replay_preset=ReplayPreset.LATEST,
                           num_requested=batch_size)
        # subsequent FetchRequests sent to refill flow-control window

    async for response in stub.Subscribe(request_iter(), metadata=metadata):
        for event in response.events:
            schema = schema_cache.setdefault(
                event.event.schema_id,
                fastavro.parse_schema(json.loads(
                    (await stub.GetSchema(SchemaRequest(schema_id=event.event.schema_id),
                                          metadata=metadata)).schema_json)),
            )
            payload = fastavro.schemaless_reader(io.BytesIO(event.event.payload), schema)
            yield (event.replay_id, payload)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from salesforce.auth import AuthStrategy


@dataclass
class PubSubConsumer:
    auth: AuthStrategy
    endpoint: str = "api.pubsub.salesforce.com:7443"

    async def subscribe(
        self,
        topic: str,
        *,
        replay_id: bytes | None = None,
        batch_size: int = 100,
    ) -> AsyncIterator[tuple[bytes, dict[str, Any]]]:
        raise NotImplementedError(
            "Pub/Sub consumer requires generated gRPC stubs. Run "
            "`scripts/gen_pubsub_proto.sh` to fetch the proto and emit "
            "`salesforce/pb/pubsub_api_pb2*.py`."
        )
        yield  # pragma: no cover  # noqa: RUF100
