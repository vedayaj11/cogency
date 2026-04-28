# Cogency

Standalone agentic case management platform that sits on top of Salesforce Service Cloud as a hybrid read-from-local, write-to-Salesforce intelligence layer.

See [cogency_product_requirement_document.md](./cogency_product_requirement_document.md) for the full PRD.

## Status

Pre-development monorepo scaffold. The PRD targets a 12-week MVP with seven capabilities:

1. Smart Case Intake & Structured Creation
2. AOP Engine (Agent Operating Procedures) — the spine
3. Unified Case Workspace + AI Co-Pilot
4. Meta-Agent + Structured Handoff
5. Agent Inbox + Human-AI Collaboration
6. Eval & Observability Console
7. Guardrails & Governance Layer

## Stack (per PRD §8)

- **Backend:** FastAPI (Python 3.12), LangGraph, Temporal
- **Data:** Postgres 16 + pgvector + ParadeDB `pg_search`
- **LLMs:** Claude Sonnet 4.5 (default), Opus 4.5 (escalation/judge), Haiku 4.5 (triage)
- **Frontend:** Next.js 15 + React 19 + assistant-ui + Vercel AI SDK 6
- **Salesforce:** Bulk API 2.0 + Pub/Sub gRPC (CDC) + REST composite writes
- **Observability:** Langfuse (self-hosted)
- **Auth:** WorkOS AuthKit

## Repo layout

```
cogency/
├── apps/
│   ├── api/         FastAPI service (health, /v1 routes)
│   ├── worker/      Temporal worker (activities + workflows)
│   └── web/         Next.js 15 + React 19 + Tailwind 4
├── packages/
│   ├── salesforce/  JWT auth, Bulk 2.0, Pub/Sub gRPC, writer outbox
│   ├── schemas/     Pydantic models shared across api/worker
│   ├── aop/         AOP DSL parser, compiler, executor
│   ├── agents/      LangGraph: meta-agent, skills, copilot
│   ├── tools/       Tool registry (Salesforce mirror, RAG, refund, email)
│   ├── prompts/     Versioned prompt artifacts (synced to Langfuse)
│   ├── guardrails/  PII redaction, prompt injection, citation enforcement
│   └── evals/       Golden datasets + LLM-judge rubrics
├── db/
│   ├── alembic.ini
│   └── migrations/
├── infra/
│   ├── docker/      docker-compose.yml + Dockerfiles
│   └── render.yaml
└── scripts/
    └── dev.sh       one-shot bootstrap (compose up + migrate)
```

## Getting started

Prereqs: Docker, Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20+, pnpm 9.

```bash
# 1. Clone & install
git clone https://github.com/vedayaj11/cogency.git
cd cogency
cp .env.example .env
uv sync --all-packages
pnpm install

# 2. Start infra (Postgres+pgvector, Temporal, Langfuse) and run migrations
./scripts/dev.sh

# 3. Run the services
make api     # http://localhost:8000/health
make worker  # connects to Temporal
make web     # http://localhost:3000
```

Other URLs once services are up:
- Temporal UI → http://localhost:8233
- Langfuse → http://localhost:3001

## Make targets

| Target            | Purpose                                    |
| ----------------- | ------------------------------------------ |
| `make install`    | Install Python (uv) + Node (pnpm) deps     |
| `make up` / `down`| Start/stop docker compose infra            |
| `make api`        | Run FastAPI dev server                     |
| `make worker`     | Run Temporal worker                        |
| `make web`        | Run Next.js dev server                     |
| `make migrate`    | Apply Alembic migrations                   |
| `make fmt`        | `ruff format` + `ruff check --fix`         |
| `make lint`       | `ruff check` + `mypy`                      |
| `make test`       | `pytest -q`                                |

## What's wired vs. what's a stub

**Wired:**
- FastAPI app with `/health` and `/v1/integrations/salesforce/sync_status` routes
- Temporal worker bootstrap with sample `HealthWorkflow` + `ping` activity
- Next.js 15 starter with placeholder Workspace / Inbox / AOPs / Evals cards
- Initial Alembic migration creating `sf.*` mirror schema, `cogency.*` tables, pgvector
- Docker compose for Postgres+pgvector, Temporal (server + UI), Langfuse

**Stubbed (next milestones):**
- Salesforce sync (Bulk 2.0 backfill, Pub/Sub CDC consumer, writer outbox) — `packages/salesforce`
- AOP engine runtime executor (parser + compiler are real) — `packages/aop`
- Meta-agent LangGraph graph — `packages/agents`
- Guardrails (PII via Presidio, prompt injection via LLM Guard) — `packages/guardrails`
- Eval runner + LLM-judge — `packages/evals`
- Workspace UI, Inbox UI, AOP authoring UI — `apps/web/app/*`
