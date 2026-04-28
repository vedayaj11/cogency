# Cogency

Standalone agentic case management platform that sits on top of Salesforce Service Cloud as a hybrid read-from-local, write-to-Salesforce intelligence layer.

See [cogency_product_requirement_document.md](./cogency_product_requirement_document.md) for the full PRD.

## Status

Pre-development. Milestones 1 (scaffold) → 4 (Workspace UI) are in. The PRD targets a 12-week MVP with seven capabilities:

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
│   ├── schemas/     Pydantic contracts (CaseContext, BackfillCasesInput, RunAOPInput, ...)
│   ├── aop/         AOP DSL parser, compiler
│   ├── agents/      OpenAI LLM client, AOPExecutor, guardrail evaluator
│   ├── tools/       Tool registry + builtin tools (lookup_case, propose_refund, ...)
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

aops/
└── refund_under_500.md         reference AOP demonstrating the DSL
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

## Running an AOP

```bash
# 1. Make sure cases are in the local mirror (run a backfill — see below).
# 2. Worker must be running (registers RunAOPWorkflow).

# 3. Author + deploy the reference refund AOP:
curl -X POST http://localhost:8000/v1/aops \
  -H 'content-type: application/json' \
  -d "$(jq -Rs '{name: "refund_under_500", source_md: ., deploy: true}' < aops/refund_under_500.md)"

# 4. Trigger a run against a real case_id from the mirror:
curl -X POST http://localhost:8000/v1/aop_runs \
  -H 'content-type: application/json' \
  -d '{"aop_name": "refund_under_500", "case_id": "5003t000XXXXXXXAAA"}'
# → {"workflow_id": "...", "run_id": "...", "aop_version_id": "..."}

# 5. Read the trace:
curl http://localhost:8000/v1/aop_runs/<run_id>
```

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
- FastAPI: `/health`, `/v1/integrations/salesforce/{sync_status,connect,backfill}`, `/v1/aops`, `/v1/aop_runs`, `/v1/aop_runs/{id}`, `/v1/cases`, `/v1/cases/{id}`, `/v1/inbox`
- Temporal worker: `BackfillCasesWorkflow`, `RunAOPWorkflow`, `HealthWorkflow`
- `SalesforceClient`: JWT + Client Credentials auth, REST query/update/composite, Bulk 2.0 query lifecycle, rate-limit gauge
- `OutboxWriter` with optimistic concurrency (412 → conflict outcome)
- Async SQLAlchemy + ORM for `sf.*` and `cogency.*`; `CaseRepository.upsert_many` with system_modstamp guard
- **AOP runtime**: parser, compiler (tool/scope validation), `AOPExecutor` with OpenAI tool-calling loop, runtime guardrail evaluator (`requires_approval_if`, `halt_on`, `max_cost_usd`), per-step trace capture, cost rollup
- Built-in tools: `lookup_case`, `lookup_contact`, `verify_customer_identity`, `propose_refund`, `add_case_comment`, `update_case_status`
- Reference AOP: `aops/refund_under_500.md`
- Inbox auto-creation on `escalated_human` outcomes
- **Workspace UI** (Next.js 15, Tailwind 4, lucide icons): cases list with search/filter, 3-column case detail (customer panel + timeline + AOP run history), in-line "Run AOP" trigger, full step-by-step run trace viewer with input/output/error panes, inbox list, AOPs catalog, sync pill in app header
- Unit tests for executor + guardrails

**Stubbed (next milestones):**
- Pub/Sub gRPC consumer (`scripts/gen_pubsub_proto.sh` to fetch + generate)
- OAuth callback handler (code → token exchange + persist tenant credentials)
- Meta-agent LangGraph graph (AOP selector)
- RAG / knowledge layer (citation-grounded retrieval)
- Guardrails (Presidio PII + LLM Guard prompt-injection)
- Eval runner + LLM-judge
- Inbox actions (approve / modify / reject endpoints + UI buttons)
- AOP authoring UI (today AOPs are uploaded via API only)

## Auth flow notes

The PRD prefers JWT Bearer (§7.4). This build supports both:

- **JWT Bearer**: set `SF_CLIENT_ID`, `SF_USERNAME`, `SF_JWT_PRIVATE_KEY_PATH`. Upload the matching cert to the Connected App; pre-authorize the integration user.
- **Client Credentials**: set `SF_CLIENT_ID`, `SF_CLIENT_SECRET`. Requires the Connected App to have "Enable Client Credentials Flow" set with a Run As user.

`auth_from_credentials()` picks JWT if a private key file is present, else Client Credentials.
