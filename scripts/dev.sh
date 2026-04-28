#!/usr/bin/env bash
set -euo pipefail

# One-shot dev bootstrap: bring up infra, run migrations, print next steps.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[dev.sh] copied .env.example -> .env (edit secrets before running agents)"
fi

echo "[dev.sh] starting docker compose stack..."
docker compose -f infra/docker/docker-compose.yml up -d

echo "[dev.sh] waiting for postgres..."
until docker exec cogency-postgres pg_isready -U cogency -d cogency >/dev/null 2>&1; do
  sleep 1
done

echo "[dev.sh] creating langfuse db (if missing)..."
docker exec cogency-postgres psql -U cogency -d cogency -tc "SELECT 1 FROM pg_database WHERE datname='langfuse'" \
  | grep -q 1 || docker exec cogency-postgres psql -U cogency -d cogency -c "CREATE DATABASE langfuse"

echo "[dev.sh] applying alembic migrations..."
( cd db && uv run alembic upgrade head )

cat <<EOF

[dev.sh] ready.
  api      -> make api      (http://localhost:8000/health)
  worker   -> make worker
  web      -> make web      (http://localhost:3000)
  temporal -> http://localhost:8233
  langfuse -> http://localhost:3001
EOF
