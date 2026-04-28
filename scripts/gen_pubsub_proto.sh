#!/usr/bin/env bash
# Fetch Salesforce's pubsub_api.proto and emit Python gRPC stubs.
#
# Output:
#   packages/salesforce/salesforce/pb/pubsub_api_pb2.py
#   packages/salesforce/salesforce/pb/pubsub_api_pb2_grpc.py
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PB_DIR="$ROOT/packages/salesforce/salesforce/pb"
PROTO_URL="https://raw.githubusercontent.com/forcedotcom/pub-sub-api/main/pubsub_api.proto"

mkdir -p "$PB_DIR"
echo "[gen_pubsub_proto] fetching $PROTO_URL"
curl -fsSL "$PROTO_URL" -o "$PB_DIR/pubsub_api.proto"

touch "$PB_DIR/__init__.py"

echo "[gen_pubsub_proto] generating stubs..."
uv run python -m grpc_tools.protoc \
    -I "$PB_DIR" \
    --python_out="$PB_DIR" \
    --grpc_python_out="$PB_DIR" \
    "$PB_DIR/pubsub_api.proto"

# protoc emits files at the import root; relocate import paths so the
# generated grpc module finds the pb2 module via salesforce.pb namespace.
sed -i.bak 's/^import pubsub_api_pb2/from salesforce.pb import pubsub_api_pb2/' \
    "$PB_DIR/pubsub_api_pb2_grpc.py"
rm -f "$PB_DIR/pubsub_api_pb2_grpc.py.bak"

echo "[gen_pubsub_proto] done. Stubs in $PB_DIR"
