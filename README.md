# Cogency

Standalone agentic case management platform that sits on top of Salesforce Service Cloud as a hybrid read-from-local, write-to-Salesforce intelligence layer.

See [cogency_product_requirement_document.md](./cogency_product_requirement_document.md) for the full PRD.

## Status

Pre-development. Milestone 1 (scaffold) and Milestone 2 (Salesforce sync foundation) are in. The PRD targets a 12-week MVP with seven capabilities:

1. Smart Case Intake & Structured Creation
2. AOP Engine (Agent Operating Procedures) — the spine
3. Unified Case Workspace + AI Co-Pilot
4. Meta-Agent + Structured Handoff
5. Agent Inbox + Human-AI Collaboration
6. Eval & Observability Console
7. Guardrails & Governance Layer

## Stack

The PRD specifies Claude Sonnet 4.5 for default reasoning; this build uses **OpenAI** instead (per project decision). All other choices follow PRD §8.1:

- **Backend:** FastAPI (Python 3.12), LangGraph, Temporal
- **Data:** Postgres 16 + pgvector + ParadeDB `pg_search`
- **LLMs:** OpenAI (`gpt-4o` default, `gpt-4o-mini` triage); Anthropic kept as optional cross-family judge
- **Frontend:** Next.js 15 + React 19 + assistant-ui + Vercel AI SDK 6
- **Salesforce:** Bulk API 2.0 + Pub/Sub gRPC (CDC) + REST composite writes
- **Observability:** Langfuse (self-hosted)
- **Auth:** WorkOS AuthKit

## Repo layout

```
cogency/
├── apps/
│   ├── api/         FastAPI service
│   ├── worker/      Temporal worker (activities + workflows)
│   └── web/         Next.js 15 + React 19 + Tailwind 4
├── packages/
│   ├── db/          SQLAlchemy async session, ORM models, repositories
│   ├── salesforce/  JWT auth, Bulk 2.0, REST client, Pub/Sub gRPC, writer outbox
│   ├── schemas/     Pydantic contracts (CaseContext, BackfillCasesInput, ...)
│   ├── aop/         AOP DSL parser, compiler
│   ├── agents/      LangGraph: meta-agent, skills, copilot
│   ├── tools/       Tool registry
│   ├── prompts/     Versioned prompt artifacts
│   ├── guardrails/  PII redaction, prompt injection, citation enforcement
│   └── evals/       Golden datasets + LLM-judge rubrics
├── db/
│   ├── alembic.ini
│   └── migrations/  0001 initial schema, 0002 dev tenant seed
├── infra/
│   ├── docker/      docker-compose.yml + Dockerfiles
│   └── render.yaml
└── scripts/
    ├── dev.sh                  one-shot bootstrap
    ├── gen_pubsub_proto.sh     fetch SF Pub/Sub proto + emit gRPC stubs
    └── backfill_cases.py       trigger a Bulk 2.0 backfill via Temporal
```

## Getting started

Prereqs: Docker, Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20+, pnpm 9.

```bash
git clone https://github.com/vedayaj11/cogency.git
cd cogency
cp .env.example .env  # then fill in OPENAI_API_KEY, SF_*, etc.
uv sync --all-packages
pnpm install

./scripts/dev.sh         # boots Postgres+pgvector, Temporal, Langfuse; runs migrations
make api                 # http://localhost:8000/health
make worker              # connects to Temporal, registers workflows + activities
make web                 # http://localhost:3000
```

Other URLs:
- Temporal UI → http://localhost:8233
- Langfuse → http://localhost:3001

## Running a Salesforce backfill

```bash
# 1. Make sure .env has SF_CLIENT_ID, SF_CLIENT_SECRET (or JWT key + USERNAME), SF_LOGIN_URL, SF_API_VERSION.
# 2. Worker must be running.
make worker

# 3. In a second shell, trigger the backfill (CLI):
uv run python scripts/backfill_cases.py
# or via the API:
curl -X POST http://localhost:8000/v1/integrations/salesforce/backfill \
  -H 'content-type: application/json' -d '{}'

# 4. Watch progress in Temporal UI: http://localhost:8233
# 5. Read state:
curl http://localhost:8000/v1/integrations/salesforce/sync_status
```

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
- FastAPI app with `/health`, `/v1/integrations/salesforce/{sync_status,connect,backfill}`
- Temporal worker with `BackfillCasesWorkflow` + `backfill_cases` activity
- `SalesforceClient`: JWT Bearer + Client Credentials auth, REST query/update/composite, Bulk 2.0 query lifecycle (submit, poll, stream results, delete), rate-limit gauge
- `OutboxWriter` with optimistic concurrency (412 → conflict outcome)
- Async SQLAlchemy session, ORM models for `sf.case/contact/account/user/sync_state`, `cogency.{tenants,aops,aop_versions,aop_runs,aop_steps,agent_inbox_items,audit_events}`
- `CaseRepository.upsert_many` with system_modstamp guard (out-of-order events never clobber newer data)
- Next.js 15 starter
- Initial migration + dev tenant seed; pgvector extension installed

**Stubbed (next milestones):**
- Pub/Sub gRPC consumer — schema documented; `scripts/gen_pubsub_proto.sh` fetches Salesforce's proto and emits stubs
- OAuth callback handler (code → token exchange + persist tenant credentials)
- AOP runtime executor (parser + compiler are real)
- Meta-agent LangGraph graph
- Guardrails (Presidio + LLM Guard)
- Eval runner + LLM-judge
- Workspace UI, Inbox UI, AOP authoring UI

## Auth flow notes

The PRD prefers JWT Bearer (§7.4). This build supports both:

- **JWT Bearer**: set `SF_CLIENT_ID`, `SF_USERNAME`, `SF_JWT_PRIVATE_KEY_PATH`. Upload the matching cert to the Connected App; pre-authorize the integration user.
- **Client Credentials**: set `SF_CLIENT_ID`, `SF_CLIENT_SECRET`. Requires the Connected App to have "Enable Client Credentials Flow" set with a Run As user.

`auth_from_credentials()` picks JWT if a private key file is present, else Client Credentials.
