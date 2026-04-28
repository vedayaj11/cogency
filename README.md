# Cogency

Standalone agentic case management platform that sits on top of Salesforce Service Cloud as a hybrid read-from-local, write-to-Salesforce intelligence layer.

See [cogency_product_requirement_document.md](./cogency_product_requirement_document.md) for the full PRD.

## Status

Pre-development. The PRD targets a 12-week MVP with seven capabilities:

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
