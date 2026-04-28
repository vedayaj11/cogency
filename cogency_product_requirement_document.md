# Cogency: Product Requirements Document

## Standalone Agentic Case Management Platform (Salesforce-Integrated)

**Version:** 1.0 (PRD for 3-month MVP build)
**Audience:** Founding engineering team, design partner stakeholders
**Status:** Development-ready

---

## 1. Executive Summary

**Cogency is a standalone, agent-first case management platform that sits *on top of* Salesforce Service Cloud as a hybrid read-from-local, write-to-Salesforce intelligence layer.** It is not a managed package, not a Salesforce-native app, and not a Dataclaw vertical — it is an independent product that uses Salesforce as the system of record while providing a fundamentally better resolution surface powered by a meta-agent, an AOP (Agent Operating Procedures) engine, and a citation-grounded knowledge layer.

The market opportunity is sharp: in 2025–26, the agentic CX category converged on a single architectural pattern — **NL-defined procedures (AOPs/Procedures/Playbooks/Journeys) compiled into deterministic-when-needed agent workflows, evaluated via simulation, deployed with versioning, and observed via traces.** Sierra ($10B, $100M ARR in 7 quarters), Decagon ($4.5B, Coatue/Index Series D Jan 2026), Intercom Fin (40M+ resolutions, 67% rate), and Salesforce Agentforce 360 all ship this pattern. Yet none of them solve the **Salesforce-anchored enterprise** that wants AI-agent autonomy *without* abandoning their CRM as the system of record. That is Cogency's wedge.

The 3-month MVP ships **seven complete capabilities** built around one demonstrable thesis: *an AI agent resolves real cases end-to-end via Agent Operating Procedures, with full observability, guardrails, and clean human handoff, while Salesforce remains the source of truth.* Every architectural decision below — Postgres + pgvector as the local mirror, Bulk API 2.0 + Pub/Sub CDC for sync, JWT Bearer OAuth, LangGraph + Temporal for agent durability, Claude Sonnet 4.5 as the default reasoning model, Langfuse for observability — is opinionated to ship in 12 weeks with a 4–6 person team.

The bar to clear at week 12: **≥60% autonomous resolution on a 100-case benchmark from a real design partner**, **≥85% golden-set pass rate before any AOP deploy**, **<2% hallucination rate (claims without citation)**, and **<$0.40 average cost per resolved case** — numbers that match the lower bound of public benchmarks from Sierra and Decagon and are demonstrable in a 30-minute investor or buyer demo.

---

## 2. Product Vision & Positioning

### 2.1 Vision
**The agent layer for Salesforce-anchored enterprises.** A product that makes it possible for an organization with hundreds of thousands or millions of cases in Service Cloud to deploy autonomous agents in weeks — not the multi-quarter Agentforce implementations that 31% of customers reportedly abandon — without ripping out Salesforce or accepting Salesforce's pricing model and operational tax.

### 2.2 Positioning Statement
For **mid-market and enterprise CX teams already running Salesforce Service Cloud** who need **autonomous, AOP-driven case resolution with enterprise-grade evals and observability**, **Cogency** is **a standalone agentic case management platform** that **integrates via OAuth, mirrors data locally for sub-100ms agent reads, and writes through Salesforce so the CRM stays the system of record** — unlike **Agentforce (expensive, locked-in, complex)**, **Sierra/Decagon (require platform replacement, no Salesforce CRM coupling)**, or **building it yourself (12+ months and an agent infra team)**.

### 2.3 Why now
1. **AOPs have converged as the dominant abstraction.** Decagon coined them; Fin (Procedures), Salesforce (Agent Script), Sierra (Journeys), Ada (Playbooks) all shipped functional equivalents. The category has agreed on the shape; the race is on developer ergonomics, eval depth, and integration breadth.
2. **Per-resolution pricing is the new norm**, set by Intercom's $0.99/outcome anchor in 2023 and now adopted by Sierra, Zendesk, Decagon. Buyers expect outcome-based economics, which kills incumbent per-seat models — and Salesforce's three concurrent pricing models ($2/conversation, $0.10/action Flex Credits, $125/seat add-on) signal market confusion Cogency can exploit with pricing clarity.
3. **Enterprise procurement has crystallized requirements**: SOC 2, prompt-injection defense, PII redaction, RAG with citations, prompt versioning, golden-set evals, audit trails. None are negotiable in 2026; vendors who didn't build them in 2024–25 are stuck.
4. **Salesforce CDC + Pub/Sub API are mature.** Pub/Sub API is GA, gRPC-flow-controlled, with ~1–3s end-to-end latency. The hybrid mirror pattern — once Heroku Connect's exclusive turf — is now reproducible by any team with the right architectural recipe (laid out in §7).

### 2.4 Differentiation vs. nearest competitors
| Competitor | What they do well | Where Cogency wins |
|---|---|---|
| **Salesforce Agentforce 360** | Tightest CRM coupling, AgentExchange marketplace, Atlas reasoning | Faster TTV (<1 hour install vs. multi-month), pricing clarity, no Data Cloud lock-in, modern eval/obs stack out of the box |
| **Sierra** | Best-in-class voice, τ-bench thought leadership, Agent Data Platform | Salesforce-native sync (Sierra requires CDP-like ADP); enterprise IT keeps SF as SoR; lower TCO for SF-anchored orgs |
| **Decagon** | AOPs, Watchtower QA, Voice 2.0, Proactive Agents | We adopt AOPs as our core abstraction *and* pair with Salesforce write-back; Decagon doesn't deeply integrate Salesforce as SoR |
| **Intercom Fin** | $0.99/outcome pricing, Procedures + Simulations, MCP | Fin is messenger-anchored; Cogency is case/CRM-anchored — different buyer, different workflow |
| **Zendesk + Forethought** | Resolution Platform, Forethought's Browser Agent, broad acquisitions | Cogency targets Salesforce orgs (Zendesk/SF rarely co-exist as primary); cleaner product without 6 acquisition seams |

---

## 3. Target Users & Personas

### Buyer personas (who signs the contract)
**P1 — VP of Customer Experience / Head of Support** at a $100M–$2B ARR SaaS or e-commerce company running Salesforce Service Cloud Enterprise/Unlimited. Cares about: cost per resolution, CSAT, deflection rate, agent productivity. Pain: Agentforce is too expensive and complex; existing point AI tools don't talk to Salesforce.

**P2 — CX Operations / RevOps Director.** Owns Service Cloud configuration. Cares about: not breaking workflows, audit trails, integration hygiene, training friction. Pain: every AI vendor wants to replace pieces of Service Cloud; they want augmentation, not replacement.

### Builder personas (who configures the product)
**P3 — CX Architect / Solutions Engineer.** Authors AOPs, defines escalation policies, curates the knowledge base. Technical but non-developer. Reads SOPs, writes prompts. The Decagon "Agent PM" archetype.

**P4 — Salesforce Admin.** Maintains the Service Cloud org. Installs and configures Cogency's connected app, manages permissions, handles sandbox refreshes. Needs the integration to "just work."

### End-user personas (who works inside the product daily)
**P5 — Tier 1/2 Support Agent.** Handles cases the AI escalated. Lives in the Unified Workspace 8 hours a day. Needs: zero context-switching, fast workspace loads, trust in AI suggestions, ability to override fearlessly.

**P6 — Senior Agent / Approver.** Reviews AI-proposed actions exceeding risk thresholds (refunds, retentions, sensitive policy decisions). Lives in the Agent Inbox.

**P7 — CX Ops / Data Analyst.** Lives in the Eval Console and Executive View. Curates golden sets, runs regression tests, watches production drift, reports KPIs to leadership.

---

## 4. Competitive Landscape (Brief)

### 4.1 Table-stakes in 2026 (every competitor ships these)
RAG over docs with NL-defined retrieval; single agent across multi-channel (chat + email minimum); NL-defined workflows (AOPs/Procedures/Playbooks); API tool calling; human handoff with summary; per-resolution/outcome pricing; agent-assist copilot for humans; multilingual (40+ languages); knowledge gap detection; basic observability/trace logging; testing sandbox; PII redaction; SOC 2/GDPR/HIPAA compliance; MCP support.

### 4.2 Cutting-edge in 2026 (only 1–2 leaders have each)
Authoritative public benchmark authorship (only Sierra: τ³-bench Mar 2026); voice with full digital parity (Sierra, Decagon, Ada); outbound proactive agents (Decagon Proactive Agents Mar 2026); cross-conversation memory (Sierra ADP, Decagon user memory); GitHub-style multiplayer dev (Sierra Workspaces); large-scale synthetic simulation (Ada Testing at Scale); meta-agents that build/improve agents (Decagon Duet, Zendesk Resolution Learning Loop); adherence supervisor watchdog AIs (Ada, Decagon Watchtower); browser-agent for legacy systems (Forethought, now Zendesk); single-click ChatGPT distribution (Sierra); PCI L1 in-conversation payment (Sierra).

### 4.3 What Cogency adopts as core MVP (vs. defers)
**Adopt as core:** AOPs, citation-grounded RAG, eval/observability with golden sets, prompt versioning, PII redaction + prompt injection defense, structured agent-to-agent handoff, agent inbox, agent persona/identity, Salesforce-native sync.

**Defer to v2/v3:** Native voice agents (transcripts-only in MVP), proactive outreach, customer-facing chat widget, fine-tuning loops, A/B testing in production, predictive ML for churn/SLA, visual DAG builder, skill marketplace, browser agents.

### 4.4 Salesforce Agentforce — the elephant in the room
Agentforce is the obvious incumbent risk. Three observations shape strategy: **(1)** Agentforce's complexity is real — Constellation reports only 3,000 of 5,000 announced Agentforce deals were paid; Oliv.ai analysis suggests only 31% of implementations remain active beyond 6 months. **(2)** Pricing is chaotic — three concurrent models ($2/conversation, Flex Credits, per-seat add-ons starting $125/user/mo, Agentforce 1 Editions at $550/user/mo); buyer confusion is a sales lever. **(3)** Atlas Reasoning Engine + Agent Script genuinely deliver in tightly-scoped Salesforce-native workflows, but anything cross-system (your billing system, your custom internal tools, your data warehouse) requires Data 360 / Intelligent Context investment. Cogency's wedge is "all the agent value, none of the platform tax."

---

## 5. Feature Gap Analysis

### 5.1 Decision matrix on the original 15 sections + 19 candidate additions

| Original section | Action | Disposition |
|---|---|---|
| 1. Agentic Command Center | **Keep, simplify** | MVP — core conversational shell + action feed; reasoning panel auto-rendered from traces, not a custom UI |
| 2. Smart Case Intake & Creation | **Keep, sharpen** | MVP — concrete acceptance criteria specified (§6.1) |
| 3. Unified Case Workspace | **Keep, simplify** | MVP — Customer 360 is a Salesforce pull-through, not a CDP rebuild |
| 4. Autonomous Case Resolution Engine | **Replace with AOP Engine** | MVP — dissolved into §6.2 AOP Engine |
| 5. Agent Skill System | **Replace with AOP Engine** | MVP — skills become AOP-callable tools; marketplace deferred to v3 |
| 6. Case Intelligence & Insights | **Simplify heavily** | MVP keeps root-cause clustering + heuristic trends; predictive ML → v2 |
| 7. Human-AI Collaboration Controls | **Keep, expand** | MVP — adds Agent Inbox as first-class surface |
| 8. Omnichannel Communication Hub | **Cut to email + web form + SF case sync** | MVP scope; voice = transcript ingestion only; WhatsApp/SMS/native voice → v2; translation → v2 |
| 9. Workflow & Automation Builder | **CUT — replaced by AOP Engine** | DAG builders are 2023; NL-first AOPs ship faster, demo better |
| 10. Knowledge & Memory Layer | **Keep, sharpen** | MVP — hard requirement: every factual claim has a citation; no citation = no claim |
| 11. Simulation & Training Mode | **Reframe as Agent Regression Testing** | MVP — replays + golden sets; "train humans" semantics cut |
| 12. SLA & Risk Monitoring | **Simplify to rules-based** | MVP — ML-based breach prediction → v2 |
| 13. Governance, Compliance & Observability | **Split into 3 sections** | MVP — (a) RBAC/audit, (b) Eval/Obs Console, (c) Guardrails layer; all core |
| 14. Meta-Agent | **Keep, narrow** | MVP — router with structured handoff payloads; not a full multi-agent platform |
| 15. Executive View | **Keep, simplify** | MVP — KPI dashboard with 6 metrics; cohort analysis → v2 |

### 5.2 Additions that make MVP (sourced from gap analysis)
- **AOP Engine** (the new spine, replaces §4 + §5 + §9)
- **Agent Inbox** (escalation queue with approve/override/edit)
- **Eval & Observability Console** (golden sets, regression diffs, drift alerts, trace explorer, prompt versioning)
- **Guardrails Layer** (PII redaction, prompt injection defense, hallucination detection via citation enforcement)
- **Action policies / per-action permission scopes** (Salesforce Trusted Agent Identity equivalent)
- **Sandbox dry-run mode** (preview AOP execution without side effects)
- **Cost/token budget controls + kill switch** (per-tenant, per-conversation)
- **Agent persona/identity management** (brand voice profiles)

### 5.3 Additions deferred to v2/v3
| Feature | Phase | Why deferred |
|---|---|---|
| Native voice agents (real-time ASR/TTS, barge-in) | v2 | 2-month engineering effort alone; transcript ingestion covers 80% of demo value |
| Customer-facing chat widget (deflection) | v2 | Different product surface, different security review, different SLAs |
| Proactive outreach / outbound agents | v3 | Different motion (campaign infra, consent, opt-out compliance) |
| Skill marketplace | v3 | AgentExchange took Salesforce 2 years post-launch; needs network effects |
| A/B testing in production | v2 | Needs traffic volume MVP customers won't have |
| Predictive churn risk ML | v2 | Needs ≥6 months of per-tenant historical data |
| Real-time co-browsing / screen sharing | v3 | Wrong product category (contact center, not case mgmt) |
| Customer journey graph | v2 | Sierra ADP-level capability; hard to build well |
| Real-time fine-tuning / RLHF loops | v2 | MVP version = feedback capture only; real version needs label pipeline |
| Translation / tone adjustment | v2 | Persona/voice config in MVP covers tone; translation is its own problem |
| Visual DAG workflow builder | v3 | AOPs make this redundant; ship outline view only in MVP |
| Multi-tenant browser agent (computer use) | v3 | Forethought-class; bet on MCP/API integrations instead |

---

## 6. Updated Feature Specification (MVP scope, with user stories & ACs)

The MVP ships **7 capabilities** organized below. Each capability has a primary user story, acceptance criteria, and explicit MVP/v2/v3 phasing.

### 6.1 Smart Case Intake & Structured Creation

**User Story (P3 CX Architect):** When an inbound email/web-form/Salesforce case event arrives, the agent auto-creates a structured case (priority, category, customer match, sentiment, suggested AOP) within 10 seconds so that human agents start at minute 1, not minute 15.

**MVP Acceptance Criteria:**
- AC1.1: Inbound channels: email (IMAP/SMTP + SES inbound), web form (embeddable JSON API), Salesforce case CDC events. Voice = Whisper transcript only, ingested as text.
- AC1.2: Within 10s of ingestion: case row written to local Postgres mirror AND `POST /sobjects/Case` to Salesforce; both return successfully or surface a queued retry.
- AC1.3: Auto-extracted fields: matched contact (≥0.9 confidence) or `unmatched=true`, category (from tenant taxonomy), priority (P0–P3), sentiment (-1.0 to +1.0), language, suggested AOP with confidence score.
- AC1.4: Duplicate detection: any case with cosine similarity ≥0.85 within last 7 days surfaces as `possible_duplicate_of=[case_id]`.
- AC1.5: All extractions display source spans (highlighted text) and confidence indicators in the UI.
- AC1.6: Human corrections logged to `intake_corrections` table; flagged for golden-set candidate review.
- AC1.7: 90% category-accuracy and 92% priority-accuracy on a 200-case golden eval set.

**v2:** WhatsApp/SMS channels, real-time translation, sentiment trajectory tracking, voice as a real channel.
**v3:** Multi-modal intake (image/screenshot extraction).

### 6.2 AOP Engine (Agent Operating Procedures) — the spine

**User Story (P3 CX Architect):** I author a refund procedure in plain English with structured checkpoints, so the agent executes it end-to-end with deterministic guardrails and a predictable outcome shape, and I can version, sandbox-test, and roll back without engineering involvement.

**MVP Acceptance Criteria:**
- AC2.1: Authoring UI accepts NL instructions + a structured outline (steps with: required tools, required permissions, inputs, expected outputs, fallbacks).
- AC2.2: AOP compiler validates: tool existence, permission scope coverage, input/output shape integrity, cycles. Errors surface inline with line references.
- AC2.3: Each step's tool call is wrapped as a Temporal Activity with retry policy, timeout, and idempotency key.
- AC2.4: Hard guardrails declarable: `requires_approval_if(refund_amount > 500)`, `halt_on(identity_verify_failed)`. Enforced at runtime; violations route to Agent Inbox.
- AC2.5: Versioning: every save = new immutable version; rollback in one click; prod traffic split by version (v1 default; configurable per-tenant).
- AC2.6: Sandbox dry-run mode: agent plans actions but routes side-effecting tools to a preview log instead of executing.
- AC2.7: Execution trace captured per step (input, reasoning summary, tool call, output, latency, cost) and viewable in Trace Explorer.
- AC2.8: **Demo target: 3 reference AOPs (refund, password reset, subscription change) resolving ≥60% of matching cases end-to-end on a 100-case eval set.**

**v2:** AOP Copilot (LLM authors AOPs from SOP docs), conditional branching DSL extensions, AOP composition (sub-AOPs as reusable building blocks).
**v3:** Public AOP marketplace, AOP-from-conversation-mining (Decagon Duet equivalent).

### 6.3 Unified Case Workspace + AI Co-Pilot

**User Story (P5 Support Agent):** When I pick up an escalated case, I see one screen with full context (Salesforce Customer 360, case timeline, prior AI actions/reasoning) and an inline co-pilot drafts replies grounded in policy with clickable citations.

**MVP Acceptance Criteria:**
- AC3.1: Workspace loads in <2s p95. Layout: customer panel (Salesforce pull-through), case timeline (every action, AI or human, time-stamped), AOP execution log (collapsible), suggested next actions panel, co-pilot chat thread.
- AC3.2: Co-pilot drafted replies cite ≥1 KB source per factual claim; clicking a citation opens the source with span highlighted.
- AC3.3: Agent can accept / edit / reject drafts; rejection reason captured to feedback queue.
- AC3.4: "Why?" panel exposes: AOP step, model used, confidence score, alternatives the agent considered.
- AC3.5: Handoff from AI: every escalated case carries a structured `handoff_summary` so agents never have to ask "what's the issue?"
- AC3.6: First-token latency p95 <8s on co-pilot stream; full draft p95 <20s.

**v2:** Multi-language co-pilot, voice transcription real-time inline, screen recording playback for cases that started as screen-share.
**v3:** Multi-modal input (paste screenshot, agent extracts).

### 6.4 Meta-Agent + Structured Handoff

**User Story (P3 CX Architect / system):** A single orchestrator decides which AOP to run, when to invoke a human, and carries structured context across handoffs (AI→AI, AI→human) so we never lose state.

**MVP Acceptance Criteria:**
- AC4.1: Meta-agent (Claude Sonnet 4.5) takes a structured case context and emits: `{selected_aop_id, confidence, reasoning, fallback_aop_id}`.
- AC4.2: Confidence threshold (configurable per tenant, default 0.7) triggers human-routing if not met.
- AC4.3: Handoff payload schema: `{summary, completed_steps, attempted_actions, pending_decisions, recommended_next, customer_state_snapshot, citations}`. Stored as JSONB, attached to the case.
- AC4.4: Agent persona/identity: each AOP can declare a `persona_id` (brand voice profile = system prompt + tone rubric + golden examples). Persona version-controlled.
- AC4.5: Multi-agent collaboration (basic): AOP A can invoke AOP B as a sub-agent with its own scoped context window; results bubble back to A.

**v2:** Dynamic AOP selection (LLM-orchestrated chaining), agent2agent (A2A) protocol support, persona A/B testing.
**v3:** Federated multi-agent across tenants/orgs (cross-org skill borrowing).

### 6.5 Agent Inbox + Human-AI Collaboration

**User Story (P6 Senior Agent):** I have a queue of cases the AI escalated to me with reason, suggested action, and one-click approve/override/edit, so I can supervise 5× more cases than I could handle directly.

**MVP Acceptance Criteria:**
- AC5.1: Inbox view sorted by SLA proximity × priority × escalation reason; filterable by AOP, agent persona, customer tier.
- AC5.2: Each item shows: AI's recommended action, confidence, reasoning summary, full trace link, approve/modify/reject CTAs.
- AC5.3: Approval thresholds configurable: monetary (`refund > $X`), category (e.g., legal/medical), customer tier (enterprise → senior approver). Routes to designated approver list.
- AC5.4: Override at any step: human override → captured to `override_events` table → flagged for golden-set candidate review.
- AC5.5: All actions logged with actor (human user_id OR `agent:{persona}@{aop_version}`), timestamp, action, before/after state. Exportable as CSV for compliance.
- AC5.6: "Take over" button: human assumes the conversation; AI exits to assist-only mode.

**v2:** Bulk approval, approval delegation/OOO routing, mobile push notifications.
**v3:** Approval workflows with multi-step chains (legal → compliance → CFO).

### 6.6 Eval & Observability Console

**User Story (P7 CX Ops Analyst):** Before shipping a new AOP version, I run it against a golden test set, see pass rates, regressions, and side-by-side trace diffs vs. the prior version — and the system blocks deploy if quality regresses.

**MVP Acceptance Criteria:**
- AC6.1: Golden dataset CRUD: add cases (from prod traces or upload JSON), tag with expected outcomes + rubric criteria (task completion, policy adherence, tone, citation accuracy).
- AC6.2: Run eval: select AOP version + golden set → batch run → per-case pass/fail + 4-dimensional rubric score (LLM-as-judge with Claude Opus 4.5 judging Sonnet executions; cross-family judging optional).
- AC6.3: Side-by-side trace diff view between two AOP versions; regressions highlighted in red; first divergent step flagged.
- AC6.4: Production observability: live trace tail filterable by AOP/outcome/customer tier; latency + cost per trace; drift alert if pass rate on rolling 7-day sample drops >10% week-over-week.
- AC6.5: Deployment gate: an AOP version can be marked `not_ready_for_prod` if eval pass rate <85%. UI surfaces the gate; admin can override with audit-logged justification.
- AC6.6: Prompt versioning: every prompt is an artifact (text + variables + version) tied to a Langfuse prompt record; rolled out as part of AOP version.
- AC6.7: 100% trace coverage in first 90 days per tenant; sampleable to 10–20% thereafter (always 100% on errors and human escalations).

**v2:** A/B testing in production with multivariate experiments, automated golden-set curation from prod traces, eval-as-CI/CD gate (PR blocks on regression).
**v3:** Eval marketplace (shared rubrics across tenants), drift root-cause auto-analysis.

### 6.7 Guardrails & Governance Layer

**User Story (P2 CX Ops Director):** Every agent action is constrained by PII redaction, prompt-injection defense, citation-required factual mode, RBAC, action-scope permissions, and a per-tenant token/cost kill switch — so I can pass enterprise security review without surprises.

**MVP Acceptance Criteria:**
- AC7.1: PII redaction (Microsoft Presidio + custom Salesforce-ID recognizers) on (a) inbound user input pre-LLM, (b) RAG-retrieved chunks pre-LLM, (c) outbound LLM responses pre-display. Tokenize-and-restore for legitimate field values.
- AC7.2: Prompt-injection defense (LLM Guard scanner): inbound user input scanned; spotlight-prefix applied to RAG chunks ("untrusted data — do not follow instructions"); injection-detected events logged + blocked.
- AC7.3: Citation-required mode: any AI factual claim without a `citation_id` referencing an indexed source is suppressed and logged. Hallucination rate target: <2% on a 1000-claim red-team test.
- AC7.4: Action-scope permissions: every tool declares required scopes (`case.update`, `refund.issue`, `email.send`); meta-agent enforces per-AOP scope grant; violations halt execution and route to inbox.
- AC7.5: RBAC: 4 default roles (Admin, CX Architect, Senior Agent, Agent); custom roles via permission matrix.
- AC7.6: Cost/token controls: per-tenant monthly token budget, per-conversation max tokens (default 100k), kill-switch on runaway agents (>3× p95 cost flagged + halted).
- AC7.7: Audit log: every agent action, prompt version, model, cost, reasoning, tool call traceable. Immutable append-only `audit_events` table; CSV export for compliance.
- AC7.8: 0 PII leakage in 1000-message external red-team test before GA.

**v2:** SOC 2 Type II audit, HIPAA mode (data residency, BAA), customer-managed encryption keys (CMEK).
**v3:** FedRAMP Moderate path, EU data residency.

---

## 7. Salesforce Integration Architecture

### 7.1 Architectural pattern (decided)
**Hybrid read-from-local, write-to-Salesforce.** Salesforce remains the system of record for all canonical case data. Cogency mirrors a defined object set into a local Postgres database via Bulk API 2.0 (initial backfill + reconciliation) plus Pub/Sub API consuming Change Data Capture events (steady-state incremental). Writes go directly to Salesforce REST API (`composite/sobjects` for batch, single PATCH for conflict-sensitive) with an outbox pattern; CDC echoes confirm durability.

### 7.2 Sync stack (decided)
| Concern | Choice | Rationale |
|---|---|---|
| Initial backfill | **Bulk API 2.0 query w/ PK Chunking** (chunkSize=100k) | Required for tables >10M rows; ~2k records/sec throughput; minimal API quota cost |
| Steady-state incremental | **Pub/Sub API (gRPC) consuming CDC** on `/data/CaseChangeEvent`, etc. | 1–3s latency; flow-controlled; ReplayId-based replay; modern (CometD is legacy) |
| Reconciliation backstop | **Nightly `getUpdated()`/`getDeleted()` per object** + weekly Bulk count check | Catches CDC gaps from outages >3 days (CDC retention limit) |
| Writes | **REST `composite/sobjects` PATCH** (200 records/call) for batch; single PATCH w/ `If-Unmodified-Since` for conflict-sensitive | Composite = 1 API call regardless of row count; conditional update prevents lost updates |
| Skipped (legacy) | PushTopic, generic Streaming events, CometD | Salesforce explicitly deprecated in favor of Pub/Sub |

### 7.3 Watermarking (decided)
**Watermark on `SystemModstamp`, not `LastModifiedDate`.** Reasoning: SystemModstamp is indexed, monotonic, advances on system/automation/encryption changes; LastModifiedDate is not indexed and can be backdated during data migrations. Advance with 60s overlap to absorb clock skew; dedupe by primary key on apply.

```sql
CREATE TABLE sf_sync_state (
  org_id        uuid,
  sobject       text,
  channel       text,                 -- 'bulk', 'cdc', 'getupdated'
  watermark_ts  timestamptz,
  cdc_replay_id bigint,
  last_run_at   timestamptz,
  last_status   text,
  PRIMARY KEY (org_id, sobject, channel)
);
```

### 7.4 Auth (decided)
**JWT Bearer flow per org with a dedicated integration user.** Web Server flow only for the initial admin install/consent ceremony (to capture admin's blessing of scopes). Pre-authorize the integration user via the Connected App's "Admin approved users" policy. Cache access tokens (~2h lifetime); never request more than one access token per 20 min per Salesforce guidance. Private signing key stored in AWS KMS / HashiCorp Vault. Annual cert rotation supported via multi-cert Connected App.

**Scopes requested:** `api`, `refresh_token offline_access` (for fallback), nothing else. Avoid `full` and `web`.

### 7.5 Conflict resolution (decided)
**Salesforce-wins by default with optimistic concurrency on writes.** On every write: `PATCH` with `If-Unmodified-Since` derived from local mirror's `LastModifiedDate`. On 412 Precondition Failed → conflict path: refetch, present 3-way merge UI (their/yours/base) for human; for headless agentic writes → DLQ with diff and "agent re-evaluate" trigger.

On CDC apply: `INSERT ... ON CONFLICT (id) DO UPDATE WHERE EXCLUDED.system_modstamp > sf.case.system_modstamp` — out-of-order events never clobber newer data.

For local-origin writes awaiting CDC echo: `pending_sync=true` flag; filter own writes from re-application via `ChangeEventHeader.changeOrigin`.

### 7.6 Rate-limit handling (decided)
- Parse `Sforce-Limit-Info` header on every response → in-memory token bucket per org.
- Hard ceiling: never exceed 50% of daily REST allocation; throttle non-critical reads at 50%; pause non-write traffic at 80%.
- On `REQUEST_LIMIT_EXCEEDED` / 429: exponential backoff with full jitter; honor `Retry-After`.
- Per-Bulk-job poll cadence: 10s on small jobs, 60s on large.
- Alarms: `cdc_lag > 5min`, `dlq_depth > 100`, `api_usage > 80%`, `replay_id_invalid`.

### 7.7 Schema mirror (decided objects)
`sf.account`, `sf.contact`, `sf.user`, `sf.case`, `sf.case_comment`, `sf.email_message`, `sf.knowledge_kav`, `sf.task`, `sf.content_version`, `sf.content_document_link` (modern files; skip legacy `sf.attachment` unless customer requires).

Custom fields: **JSONB by default** (`custom_fields jsonb`, GIN index); promote to real column only when (a) hot filter, (b) needs FK constraint, (c) referential reporting. Describe API metadata cached 24h; invalidated on `MetadataChangeEvent`.

### 7.8 Operational defaults
- Per-org dedicated sync workers (blast-radius isolation).
- One Postgres schema per ≤50 orgs, partitioned single-schema by `org_id` for >50.
- Initial backfill plan: User → Account → Contact → Case → CaseComment → EmailMessage → Task → Knowledge. 5M cases ≈ 40–50 min via Bulk PK Chunking.
- Bridge gap during backfill: start CDC consumer at `replay -1` (newest only) and buffer; drain post-backfill applying only events with `system_modstamp > backfill_start`.
- Sandbox refresh = recreate connection (Heroku Connect's pattern); build into control plane.

### 7.9 Reference architecture (text diagram)

```
┌────────── Salesforce Org ──────────┐
│  Cases / Email / Account / Contact │
│  CDC Event Bus  (/data/...ChangeEvent)│
└──┬───────────┬───────────────┬─────┘
   │ Bulk 2.0  │ REST writes   │ Pub/Sub gRPC (CDC)
   │ +PK Chunk │ composite/    │ ReplayId persisted post-COMMIT
   │           │ sobjects      │
   ▼           ▼               ▼
┌──────────────────────────────────────────────┐
│   Cogency Sync Control Plane                 │
│  ┌─────────────┐ ┌──────────────┐ ┌────────┐ │
│  │ Backfill    │ │ CDC Consumer │ │ Writer │ │
│  │ Workers     │ │ (gRPC)       │ │ outbox │ │
│  └──────┬──────┘ └──────┬───────┘ └────┬───┘ │
│         ▼               ▼              ▲     │
│  ┌─────────────────────────────────────┴──┐  │
│  │ PostgreSQL 16 + pgvector              │  │
│  │ sf.* tables (partitioned by org_id)   │  │
│  │ JSONB custom_fields, HNSW embeddings  │  │
│  │ sf_sync_state, writes_pending,        │  │
│  │ writes_dlq, audit_events              │  │
│  └────────────────────────────┬──────────┘  │
└───────────────────────────────┼─────────────┘
                                ▼
                ┌──────────────────────────────┐
                │  Cogency Agent Layer         │
                │  LangGraph + Temporal        │
                │  Meta-agent / AOP Engine     │
                │  Knowledge / RAG / Guardrails│
                └──────────────────────────────┘
```

---

## 8. Technical Architecture & Stack Recommendations

### 8.1 The "Day 1 Build This" Stack

| Layer | Choice | Reasoning (one-line) |
|---|---|---|
| **Meta-agent / planner LLM** | Claude Sonnet 4.5 (default), Opus 4.5 escalation | Best tool-use + long-context per dollar; ~80% SWE-bench Verified |
| **Skill execution LLM** | Claude Sonnet 4.5 with prompt caching | Same family = consistent schemas; cache cuts 75–90% off repeated prompts |
| **Triage / classification** | Claude Haiku 4.5 or GPT-4.1-mini | Sub-second; route to Sonnet only on uncertainty |
| **Eval judge LLM** | Claude Opus 4.5 (cross-family option: GPT-5) | Different model family from executor reduces self-bias |
| **Structured outputs** | Anthropic tool-use + Pydantic via `instructor` | Deterministic JSON; never freeform JSON mode |
| **Agent framework** | LangGraph (Python) | Best checkpointing + HITL + streaming + provider-agnostic |
| **Durable workflow engine** | Temporal (Python SDK) wrapping LangGraph nodes | Survives crashes; production agent pattern (OpenAI Codex, Replit Agent use it) |
| **Vector DB** | pgvector + pgvectorscale on the same Postgres | <10M vectors comfortable; one DB to operate; RLS multi-tenant |
| **Embeddings** | Voyage-3-large (or voyage-3.5 for cost) | 7–13% better NDCG@10 vs OpenAI text-embedding-3-large |
| **Reranker** | Voyage rerank-2.5 | 32K context; beats Cohere Rerank v3.5 by 8–13% NDCG |
| **Hybrid search** | ParadeDB `pg_search` (BM25) + pgvector + RRF fusion → rerank | Single-store hybrid; 15–40% precision lift |
| **Observability/evals** | Langfuse (self-hosted) | OSS, MIT, prompt mgmt + tracing + evals + datasets in one |
| **Backend** | FastAPI (Python 3.12) + httpx + Pydantic v2 | Same runtime as agents; native async + SSE |
| **Streaming protocol** | Server-Sent Events (SSE) | Vercel AI SDK 6 standard; survives proxies; sufficient for unidirectional |
| **Background jobs** | Temporal only | Already in stack; skip Celery/RQ |
| **Frontend** | Next.js 15 App Router + React 19 | First-party Vercel AI SDK; RSC simplifies auth-gated pages |
| **UI primitives** | Tailwind 4 + shadcn/ui | Non-negotiable default in 2026 |
| **Chat / agent UI** | assistant-ui + Vercel AI SDK 6 (`useChatRuntime`) | Built-in tool-call rendering, approval modals (`needsApproval`), threading |
| **Client state** | TanStack Query v5 + Zustand | TanStack for server state, Zustand for ephemeral UI; no Redux |
| **Auth** | WorkOS AuthKit | Free <1M MAU; SAML/SCIM at $125/connection; B2B-grade |
| **Multi-tenancy** | Shared schema + `tenant_id` + Postgres RLS (FORCE) | Cheapest, most ops-light; non-owner DB role to prevent bypass |
| **Infra** | Render (MVP) → AWS ECS Fargate + RDS (scale) | Skip Kubernetes for 3 months |
| **Document parsing** | LlamaParse (managed) for MVP; Reducto for HIPAA/regulated | Agentic OCR; layout-aware Markdown; 10K free credits |
| **Chunking** | Layout-aware semantic chunks 512–1024 tokens, 15% overlap | Use parser's native output; preserve headers + page nums for citations |
| **Re-indexing** | Hash-based incremental via Temporal scheduled workflow | Re-embed only changed chunks |
| **Guardrails** | LLM Guard (input/output) + Presidio (PII) + Pydantic validators (tool args) | Layered, lightweight; skip NeMo Guardrails for MVP |
| **Salesforce client** | `simple-salesforce` (REST) + custom gRPC client for Pub/Sub API | Avoid jsforce streaming bugs; build raw gRPC for Pub/Sub |

### 8.2 Hybrid LLM routing policy

```
Inbound case context
  │
  ├─→ Triage agent (Haiku 4.5)           [<500ms, ~$0.001]
  │     classify, dedup, sentiment
  │
  ├─→ Meta-agent (Sonnet 4.5)            [<3s, ~$0.02]
  │     select AOP, build plan
  │     │
  │     └─→ if confidence < 0.6 OR plan complexity > N
  │           → escalate to Opus 4.5     [+$0.05]
  │
  ├─→ Skill execution (Sonnet 4.5 + tools) [variable, ~$0.05–0.20/case]
  │     run AOP steps with tool calls
  │
  └─→ Async eval judge (Opus 4.5 sample 10%) [+$0.05/sampled case]
        score vs rubric → Langfuse
```

### 8.3 Architectural patterns (opinionated)
- **Every external side-effecting tool is a Temporal Activity** with `retry_policy` (max_attempts=5, exponential, jitter), `idempotency_key=case_id+step_id`, `start_to_close_timeout=60s` default.
- **Every prompt is a Langfuse prompt artifact** (versioned, variabled). Code references prompts by name + version; deploys never inline prompts.
- **Every tool input/output is a Pydantic model** shared between FastAPI handler and LangGraph node — no serialization mismatch surface.
- **Every agent run gets a `trace_id` (uuid7)** that flows across every Salesforce call, every LLM call, every UI render. Surfaced in the Workspace's "Why?" panel.

### 8.4 Repo structure

```
cogency/
├── apps/
│   ├── api/                # FastAPI + LangGraph + Temporal client + SSE
│   ├── worker/             # Temporal worker (skill activities, sync, eval)
│   └── web/                # Next.js 15 + assistant-ui + Vercel AI SDK 6
├── packages/
│   ├── agents/             # LangGraph graphs: meta_agent, skills/*
│   ├── aop/                # AOP DSL parser, compiler, executor
│   ├── tools/              # Salesforce mirror queries, RAG, email, refund APIs
│   ├── prompts/            # Versioned prompts (synced to Langfuse)
│   ├── schemas/            # Pydantic models shared across api/worker
│   ├── salesforce/         # OAuth, Bulk client, Pub/Sub gRPC, writer outbox
│   ├── guardrails/         # PII, prompt injection, citation validators
│   └── evals/              # Golden datasets + LLM-judge rubrics
├── infra/
│   ├── render.yaml         # Render blueprint
│   ├── docker/             # Per-service Dockerfiles
│   └── temporal/           # Temporal Server compose
└── db/
    ├── migrations/         # Alembic
    └── rls/                # Tenant isolation policies
```

---

## 9. Data Model

### 9.1 Salesforce mirror layer (selected — see §7.7 for full list)
`sf.account`, `sf.contact`, `sf.user`, `sf.case`, `sf.case_comment`, `sf.email_message`, `sf.knowledge_kav`, `sf.task`, `sf.content_version`, `sf.content_document_link`. Each carries `org_id`, `id` (SF 18-char), all stock fields, `custom_fields jsonb`, `embedding vector(1536)`, `system_modstamp`, `_sync_version`, `is_deleted`.

### 9.2 Cogency-native entities

```sql
-- Tenancy & auth
tenants(id, name, salesforce_org_id, plan, created_at)
users(id, tenant_id, email, role, persona_assignments, sso_connection_id)

-- AOP engine
aops(id, tenant_id, name, description, current_version_id)
aop_versions(id, aop_id, version_number, source_md, compiled_plan jsonb,
             status, created_by, created_at)         -- status: draft|ready|deployed|deprecated
aop_runs(id, tenant_id, aop_version_id, case_id, status, started_at, ended_at,
         outcome, cost_usd, token_in, token_out, trace_id)
aop_steps(id, aop_run_id, step_index, tool_name, input jsonb, output jsonb,
          reasoning text, status, latency_ms, cost_usd, error)

-- Knowledge / RAG
knowledge_sources(id, tenant_id, type, uri, last_indexed_at)
knowledge_chunks(id, source_id, tenant_id, chunk_index, text, embedding vector(1536),
                 metadata jsonb, content_hash, is_active)

-- Personas
personas(id, tenant_id, name, system_prompt, tone_rubric, golden_examples jsonb,
         version, created_at)

-- Inbox / handoffs
agent_inbox_items(id, tenant_id, case_id, escalation_reason, recommended_action,
                  confidence, status, assigned_to, sla_deadline, created_at)
handoff_payloads(id, case_id, from_actor, to_actor, payload jsonb, created_at)

-- Eval & observability
golden_datasets(id, tenant_id, name, description, created_at)
golden_cases(id, dataset_id, input_payload jsonb, expected_outcome jsonb,
             rubric jsonb, tags text[])
eval_runs(id, dataset_id, aop_version_id, status, started_at, ended_at,
          aggregate_scores jsonb)                    -- {task_completion: 0.92, citation: 0.87, ...}
eval_results(id, eval_run_id, golden_case_id, pass, scores jsonb,
             execution_trace_id, diff_vs_baseline jsonb)
prompt_versions(id, tenant_id, name, version, body, variables jsonb,
                langfuse_id, created_at)

-- Audit & governance
audit_events(id, tenant_id, actor_type, actor_id, action, target_type, target_id,
             before jsonb, after jsonb, trace_id, timestamp)
permission_grants(id, tenant_id, role, action_scope, conditions jsonb)
override_events(id, tenant_id, aop_run_id, step_id, user_id, reason, original jsonb,
                replacement jsonb, created_at)

-- Cost & budget
tenant_budgets(tenant_id, monthly_token_cap, current_month_tokens,
               per_conversation_cap, kill_switch_threshold)
```

### 9.3 Critical relationships
- `aop_runs.case_id` → `sf.case.id` (string FK across schemas; index for hot reads)
- `knowledge_chunks.tenant_id` enforced via RLS policy `USING (tenant_id = current_setting('app.current_tenant')::uuid)`
- `eval_results.execution_trace_id` → Langfuse trace (external system; URL stored)
- `audit_events` is append-only (revoke `UPDATE`/`DELETE` from app role)

---

## 10. API Surface (high-level)

REST/JSON over HTTPS, `Bearer` auth (WorkOS-issued JWT), tenant scoping via JWT claim.

### 10.1 Case management
```
POST   /v1/cases                        Create case (writes to SF + local mirror)
GET    /v1/cases/:id                    Read from local mirror; 304 cache support
PATCH  /v1/cases/:id                    Update (SF write w/ If-Unmodified-Since)
GET    /v1/cases?filters                List w/ TanStack Query pagination
POST   /v1/cases/:id/comments           Add CaseComment (SF + local)
POST   /v1/cases/:id/escalate           Force route to Agent Inbox
POST   /v1/cases/:id/take_over          Human assumes; AI → assist-only
```

### 10.2 AOP Engine
```
POST   /v1/aops                         Create AOP (returns id + draft version)
POST   /v1/aops/:id/versions            New version from source markdown
POST   /v1/aops/:id/versions/:v/compile Compile + validate (returns errors[])
POST   /v1/aops/:id/versions/:v/deploy  Deploy to prod (gated on eval pass)
POST   /v1/aops/:id/versions/:v/rollback
POST   /v1/aop_runs                     Manual run trigger {aop_version_id, case_id, dry_run}
GET    /v1/aop_runs/:id                 Run status + trace link
GET    /v1/aop_runs/:id/stream          SSE: per-step streaming events
```

### 10.3 Co-pilot / Meta-agent
```
POST   /v1/copilot/sessions             Create session for a case
POST   /v1/copilot/sessions/:id/messages  SSE-streamed reply with citations
POST   /v1/copilot/sessions/:id/feedback  thumbs ± / edit-this-response
```

### 10.4 Inbox
```
GET    /v1/inbox                        Filter by status, assignee, AOP, SLA
POST   /v1/inbox/:item_id/approve
POST   /v1/inbox/:item_id/modify        {modified_action, reason}
POST   /v1/inbox/:item_id/reject        {reason}
POST   /v1/inbox/:item_id/take_over
```

### 10.5 Eval & Observability
```
POST   /v1/golden_datasets              Create
POST   /v1/golden_datasets/:id/cases    Add case (or import from trace_id)
POST   /v1/eval_runs                    Run AOP version against dataset
GET    /v1/eval_runs/:id                Aggregate scores + per-case results
GET    /v1/eval_runs/:id/diff?baseline_run_id=
GET    /v1/traces?filters               Live trace tail (proxies Langfuse)
GET    /v1/prompts/:name/versions       Prompt history
```

### 10.6 Knowledge
```
POST   /v1/knowledge/sources            Add source (PDF upload, URL, Confluence/Drive connector)
DELETE /v1/knowledge/sources/:id
POST   /v1/knowledge/sources/:id/reindex
POST   /v1/knowledge/search             Hybrid search (BM25+vec+rerank)
```

### 10.7 Admin & integration
```
POST   /v1/integrations/salesforce/connect    Initiate OAuth Web Server flow
POST   /v1/integrations/salesforce/callback   OAuth callback
POST   /v1/integrations/salesforce/disconnect
GET    /v1/integrations/salesforce/sync_status  CDC lag, backfill progress, API usage %
POST   /v1/personas
POST   /v1/permission_grants
GET    /v1/audit_events?filters
GET    /v1/budgets/usage
```

### 10.8 Webhooks (outbound from Cogency)
- `case.escalated`, `aop_run.completed`, `aop_run.failed`, `eval_run.regressed`, `budget.threshold_crossed`, `sync.lag_alert`. Signed via HMAC-SHA256 with rotated tenant secret.

---

## 11. UX/UI Information Architecture

### 11.1 Top-level navigation
1. **Workspace** (default home for Agents) — case list + workspace detail
2. **Inbox** (default home for Senior Agents) — pending approvals queue
3. **AOPs** (CX Architects) — list, edit, version, deploy
4. **Knowledge** (CX Architects) — sources, chunks, search test
5. **Evals** (CX Ops) — golden sets, runs, diffs, prompt versions
6. **Observability** (CX Ops) — live traces, drift dashboards
7. **Insights** (Execs) — KPI dashboard
8. **Settings** (Admins) — Salesforce connection, personas, RBAC, budgets, audit log

### 11.2 Key screens

**Workspace (case detail)** — 3-column: left = customer panel (Salesforce pull-through), center = case timeline + inline co-pilot chat thread (assistant-ui), right = AOP execution log + suggested next actions + "Why?" panel. Top bar: case status, SLA countdown, escalate button, take-over button.

**AOP Editor** — split view: left = Markdown source with NL instructions and structured step blocks, right = compiled plan visualization (collapsed step tree, not a DAG canvas). Bottom drawer: validation errors, version history, "Run in sandbox" button.

**Agent Inbox** — table view sorted by SLA × priority × escalation reason. Row click opens side-panel with full context, recommended action, confidence, trace link, approve/modify/reject CTAs.

**Eval Runner** — top: dataset selector + AOP version selector + "Run" CTA. Middle: aggregate scorecard (task completion, citation accuracy, tone, policy adherence, on a 0–100 scale). Bottom: per-case results table; click row → trace diff view.

**Trace Explorer** — embedded Langfuse-style waterfall: per-step latency, cost, model, tool calls. Filters: AOP, persona, customer tier, outcome. Click a step → prompt + response + tool I/O.

**Insights Dashboard** — 6 KPI tiles + 2 trend charts:
- Tiles: autonomous resolution %, cost per case, avg first-token latency, eval pass rate, hallucination rate, SLA breach rate.
- Charts: weekly resolution rate trend; cost-per-case trend.

### 11.3 Design system
shadcn/ui base, Tailwind 4. **Inktober monochrome palette** (neutral grays + one accent — Cogency teal #0FB5BA) keeps the UI feeling like a dev tool, not a CRM. Trace explorer + AOP editor use a monospaced display font (`JetBrains Mono`) for technical density. Animations minimal (Framer Motion fade/slide only). Dark mode mandatory (CX ops live in dashboards).

---

## 12. Non-Functional Requirements

### 12.1 Performance
- Workspace detail load: p95 < 2s
- Case list: p95 < 800ms
- Co-pilot first-token: p95 < 8s
- Co-pilot full draft: p95 < 20s
- AOP simple flow execution: p95 < 30s
- AOP complex flow: p95 < 90s
- Salesforce mirror read: p95 < 100ms (local Postgres)
- CDC end-to-end lag: p95 < 5s, p99 < 30s
- Salesforce write (single PATCH): p95 < 2s

### 12.2 Scale targets (MVP → year 1)
- MVP: 1 design partner, 100k cases mirrored, 1000 AOP runs/day
- Year 1: 10 tenants, 5M cases mirrored cumulatively, 50k AOP runs/day, peak 100/min
- Storage: ~5–20 KB per case row + embeddings; 5M cases ≈ 50–100 GB in Postgres

### 12.3 Security
- SOC 2 Type II readiness checklist completed pre-GA (Type II audit in v2)
- Encryption at rest (AWS RDS encryption, KMS-managed keys); TLS 1.3 in transit
- OAuth tokens, JWT signing keys, API secrets in AWS KMS / Vault — never in env vars
- Postgres RLS with `FORCE ROW LEVEL SECURITY`; app role is non-owner; `BYPASSRLS`-free
- PII redaction layered (Presidio + custom Salesforce-ID recognizers)
- Prompt-injection defense (LLM Guard + spotlight prefixing on RAG chunks)
- External red-team test: 1000-message PII leakage probe must pass before GA
- Audit log immutable (append-only; revoke UPDATE/DELETE on table from app role)
- All actions traceable to actor (human user_id OR `agent:{persona}@{aop_version}`)

### 12.4 Compliance
- GDPR: tenant-controlled data export + deletion; per-tenant data residency disclosure
- HIPAA path in v2 (BAA + isolated environment per tenant request)
- SOC 2 Type I in MVP (control framework documented), Type II audit in v2 (3-month evidence period)
- No PHI/PCI handled in MVP (defer); explicit guardrail blocks `ssn`/`pan` patterns from being persisted

### 12.5 Observability
- 100% trace coverage in first 90 days per tenant; 10–20% sampling thereafter (always 100% on errors and human escalations)
- Langfuse self-hosted; Postgres backend
- Per-tenant cost attribution (token in/out × model × tool calls)
- Drift alerts: rolling 7-day pass-rate drop > 10% week-over-week → page on-call
- Uptime monitoring: Better Stack or Grafana Cloud; status page external (status.cogency.ai)

### 12.6 Reliability
- Target uptime: 99.5% MVP, 99.9% post-GA
- Salesforce dependency: graceful degradation banner when SF unavailable; queue writes in outbox; surface to user
- Temporal handles agent workflow durability across crashes
- Postgres: daily snapshot + PITR; Read replica added at 5M cases
- DLQ for both write outbox and CDC apply errors with admin reconciliation UI

---

## 13. 3-Month MVP Scope & Milestones

**Team assumption:** 4–6 engineers (1 frontend lead, 2 backend/agent engineers, 1 Salesforce integration specialist, 0.5–1 PM, 0.5 designer). Plus Jayadev as architect/founding eng.

**Pre-Sprint (Week 0):** Design partner signed (LOI). Salesforce sandbox provisioned. Stack decisions locked (Postgres 16, LangGraph, Temporal, Langfuse, Anthropic + OpenAI keys, WorkOS, Render). Repo skeleton, CI/CD, observability scaffold up. Golden test set design (rubrics, target 100 real cases from partner).

### Sprint 1 (Weeks 1–2): Foundations
**Goal:** Skeleton happy path end-to-end.
- WorkOS auth + tenancy + RLS + admin UI
- Salesforce OAuth (Web Server install + JWT runtime); Connected App provisioning docs
- Bulk API 2.0 backfill for Account, Contact, User, Case, CaseComment (subset of fields)
- Pub/Sub API gRPC consumer for `CaseChangeEvent`; ReplayId persisted post-COMMIT
- `composite/sobjects` writer + outbox + DLQ
- Postgres schema + Alembic migrations + RLS policies
- LangGraph + Temporal scaffolding; Langfuse self-hosted on Render
- Next.js 15 shell with Workspace, Inbox, AOP list nav; assistant-ui chat thread component
- **Demo gate:** Inbound email → case in local DB + mirrored to SF → visible in Workspace.

### Sprint 2 (Weeks 3–4): Intake Intelligence + RAG
- Smart Case Intake (AC1.1–1.7): classify, priority, sentiment, dedup, customer match
- Email ingestion (SES inbound), web form endpoint
- Knowledge ingestion pipeline: LlamaParse → chunks → Voyage embeddings → pgvector + ParadeDB BM25; RRF fusion + Voyage rerank
- Citation tracking (every chunk has stable `citation_id`)
- PII redaction layer (Presidio + custom recognizers) on inbound + RAG + outbound
- Co-pilot v1: cited replies in Workspace
- **Demo gate:** Inbound email → fully structured case + co-pilot answers grounded question with clickable citations.

### Sprint 3 (Weeks 5–6): AOP Engine v1
- AOP DSL (Markdown + structured step blocks); compiler/validator
- AOP executor (LangGraph subgraph per AOP, Temporal Activities for tools)
- Action-scope permission enforcement
- Sandbox dry-run mode
- AOP versioning + rollback
- 3 reference AOPs against design partner workflows (refund, password reset, subscription change) — built collaboratively with their CX architect
- Trace capture per step → Langfuse
- **Demo gate:** Author refund AOP in Markdown; agent executes end-to-end on sandbox; trace visible.

### Sprint 4 (Weeks 7–8): Meta-Agent + Inbox + Handoff
- Meta-agent (Sonnet 4.5) AOP selection with confidence threshold
- Persona/identity config + version control
- Agent Inbox UI with approve/override/edit/take-over
- Approval workflows (monetary, category, customer-tier rules)
- Structured handoff payloads
- Override events → feedback queue
- Sub-AOP composition (basic)
- **Demo gate:** End-to-end case → resolved by agent OR cleanly escalated to inbox with full context.

### Sprint 5 (Weeks 9–10): Eval, Observability, Guardrails
- Golden dataset CRUD + ingest from prod traces
- Eval runner with LLM-as-judge (Opus 4.5 judging Sonnet)
- 4-rubric scoring (task completion, policy adherence, tone, citation accuracy)
- Side-by-side trace diff view
- Deploy gate: < 85% pass rate → blocked
- Trace explorer (Langfuse-embedded)
- Drift alerts (7-day rolling)
- Prompt versioning UI (Langfuse-backed)
- Cost/token budget controls + kill switch + budget UI
- Prompt injection defense (LLM Guard) + spotlight prefixing
- Citation-required mode enforcement
- **Demo gate:** Ship v2 of an AOP, run eval, regression caught, rollback in 1 click.

### Sprint 6 (Weeks 11–12): Polish, Insights, Demo Hardening
- Insights Dashboard (6 KPIs + 2 trends)
- Root-cause clustering (k-means over case embeddings; surface top 5 clusters/week)
- Heuristic SLA risk scoring (rules-based)
- Performance tuning (workspace <2s, first-token <8s, AOP simple <30s)
- External 1000-message red-team test (PII + prompt injection)
- Design-partner pilot launch (real-data cutover)
- Demo script + investor dry-runs
- Documentation: install guide, AOP authoring guide, ops runbook
- **Demo gate:** Live design-partner data; 100-case demo set with ≥60% autonomous resolution, ≥85% eval pass rate, <2% hallucination rate, 0 PII leakage, <$0.40/case.

### Milestone summary
| Sprint | Weeks | Headline outcome |
|---|---|---|
| Pre | 0 | Design partner LOI; stack locked; team onboarded |
| 1 | 1–2 | Salesforce sync end-to-end; case visible in Workspace |
| 2 | 3–4 | Smart intake + cited co-pilot |
| 3 | 5–6 | AOP Engine + 3 reference AOPs running |
| 4 | 7–8 | Meta-agent + Inbox + handoff |
| 5 | 9–10 | Eval Console + Guardrails + Observability |
| 6 | 11–12 | Insights + polish + design-partner cutover + demo |

---

## 14. Out-of-Scope for MVP (deferred)

| Capability | Phase | Rationale |
|---|---|---|
| Native voice agents (real-time ASR/TTS, barge-in) | v2 (Q2 post-MVP) | 2-month engineering effort; transcript ingestion covers 80% of demo |
| WhatsApp / SMS channels | v2 | Channel adapters are mechanical; defer until first WhatsApp-heavy customer |
| Customer-facing self-service chat widget | v2 | Different product surface, security review, SLA tier |
| Proactive outbound agents (churn, NPS) | v3 | Separate motion: campaign infra, consent, opt-out compliance |
| Skill marketplace (3rd party) | v3 | Network-effect-dependent; needs scale |
| A/B testing in production (multivariate) | v2 | Needs traffic volume MVP customers won't have |
| Predictive churn risk ML | v2 | Needs ≥6 months per-tenant historical data |
| Predictive SLA breach ML | v2 | MVP uses heuristic rules; replace with ML in v2 |
| Real-time fine-tuning loops / RLHF | v2 | MVP captures feedback; real loop needs label pipeline + retraining infra |
| Real-time co-browsing / screen sharing | v3 | Wrong product category for case management |
| Customer journey graph | v2 | Sierra-ADP-class capability; complex to build well |
| Real-time translation (60+ languages) | v2 | Persona/voice covers tone in MVP |
| Visual DAG workflow builder | v3 | AOPs make this redundant |
| Browser-agent / computer-use for legacy systems | v3 | Forethought-class; bet on MCP/API integrations first |
| Multi-modal intake (images, screenshots) | v2 | Vision models cost-prohibitive at scale today |
| Mobile native apps | v3 | Web responsive in MVP |
| HIPAA compliance / BAA | v2 | Requires data residency + vendor diligence; defer until first healthcare customer |
| FedRAMP / EU residency | v3 | Long-tail compliance |
| MCP server + client | v2 | Build as a connector once 3+ customers ask |
| Dynamic LLM-orchestrated AOP chaining | v2 | Static declared chains in MVP |
| Sierra-in-ChatGPT-style distribution | v3 | Channel novelty |

---

## 15. Risks & Open Questions

### 15.1 Top risks
1. **Salesforce platform changes** (Pub/Sub API auth model, CDC retention) could force re-architecture. **Mitigation:** subscribe to Salesforce release notes; abstract sync layer behind interface; nightly `getUpdated/getDeleted` reconciliation as backstop.
2. **Design partner attrition mid-build.** **Mitigation:** sign 2 LOIs (only 1 needed) before Sprint 1; pre-write reference AOPs against generic refund/password-reset patterns so they generalize.
3. **AOP DSL becomes too constrained.** Customer wants conditional logic Markdown can't express cleanly. **Mitigation:** Sprint 3 includes a "Python escape hatch" step type (mirrors Fin's Procedures with embedded Python) — defer if scope pressure, but design DSL with this extension in mind.
4. **Hallucination rate target (<2%) misses.** **Mitigation:** citation-required mode is a hard fail-closed (no citation → no claim shown); LLM-as-judge on 100% of factual claims in eval; manual review on ambiguous categories.
5. **Cost per case overruns.** Sonnet 4.5 + Opus escalation could blow $0.40 budget on long cases. **Mitigation:** prompt caching aggressively (75–90% off); budget kill-switch; route to Haiku 4.5 for all triage; eval cost as a 5th rubric dimension.
6. **Salesforce rate limits hit during backfill of large org (10M+ cases).** **Mitigation:** Bulk API 2.0 PK Chunking + 50% API budget headroom; coordinate backfill timing with customer's Salesforce admin.
7. **Latency on co-pilot first-token >8s.** **Mitigation:** prompt caching, parallel tool calls, streaming as soon as first token available, prefetch RAG context on case open.
8. **Multi-tenant RLS bypass via app code bug.** **Mitigation:** non-owner DB role, `FORCE ROW LEVEL SECURITY`, dedicated security review in Sprint 5; CI test that explicitly tries cross-tenant queries.
9. **LangGraph + Temporal complexity tax.** Could slow Sprint 1–2. **Mitigation:** start with Temporal as job queue only (not workflow engine); introduce LangGraph checkpointing in Sprint 3 when AOP Engine needs HITL.
10. **Voyage AI was acquired by MongoDB** — pricing/access could change. **Mitigation:** abstract embedding interface; fallback to OpenAI text-embedding-3-large is one config flag.

### 15.2 Open questions to resolve in Week 0
- Which design partner? (Targets: SaaS company with 10k+ cases/month on Service Cloud)
- Salesforce edition? (Enterprise vs Unlimited affects API limits + CDC quotas)
- Which 3 reference AOPs? (Drives Sprint 3 scope)
- Cost target validated? Confirm $0.40/case is acceptable to design partner vs. their human cost
- Voice transcript provider? (Whisper API vs Deepgram — recommend Deepgram Nova-2 for accuracy + diarization)
- Hosting region for Postgres + Langfuse? (US-East default; EU customer would block)
- Pricing model? Per-resolution ($0.99 anchor) vs hybrid platform fee + per-resolution? **Recommendation:** $40k/year platform + $0.50 per autonomous resolution (cheaper than Fin, more predictable than Agentforce).
- LLM provider redundancy: Anthropic primary + OpenAI fallback configured day 1?
- Pre-launch security review vendor? (Trail of Bits, Doyensec for AI red-team)

### 15.3 Decisions explicitly deferred
- MCP server/client (v2)
- Multi-region deployment (v2)
- Self-serve onboarding (v2 — MVP is high-touch design-partner pilot)
- Free tier / trial (v2 — MVP is enterprise pilot only)
- White-label / embedded distribution (v3)

---

## 16. Success Metrics

### 16.1 Demo-day quantitative bar (Week 12 gate)
| Metric | Target | Notes |
|---|---|---|
| Autonomous resolution rate | ≥60% | On 100-case design-partner benchmark; matches Sierra/Decagon lower bound |
| AOP eval pass rate | ≥85% | Pre-deploy gate on golden set |
| Hallucination rate | <2% | Factual claims without valid citation / total factual claims |
| Co-pilot first-token p95 | <8s | Streaming start |
| AOP simple-flow execution p95 | <30s | End-to-end |
| PII leakage in red-team | 0 | 1000-message external test |
| Cost per resolved case | <$0.40 | Token + tool costs blended |
| Audit coverage | 100% | Every AI action traceable |
| Salesforce sync lag p95 | <5s | CDC end-to-end |
| Workspace load p95 | <2s | Local-mirror read |

### 16.2 Qualitative "this is real" signals
- A human agent uses the Workspace for a full 4-hour shift on partner's real queue and reports ≥30% time savings.
- A CX architect authors a brand-new AOP from a written SOP doc in <30 minutes with zero engineering help.
- An AOP rollback completes in <60 seconds with eval data justifying the rollback.
- A Salesforce admin completes the install + Connected App setup in <1 hour without ours-side hand-holding.
- An external security review (SOC 2 Type I checklist + prompt-injection demo) passes without surprises.

### 16.3 Investor narrative metrics (3 numbers to memorize)
1. **% deflection on real partner data** (vs. Reddit-on-Agentforce 46%, Anthropic-on-Fin 50.8%)
2. **Time-to-author-new-AOP** (vs. Decagon's "weeks → minutes" pitch)
3. **Cost per resolution** (vs. industry $15–25 human baseline → demo <$1)

### 16.4 Year-1 (post-MVP) targets
- 5–10 paying tenants
- $1M ARR (mix of $40k platform fees + $0.50/resolution at scale)
- 70%+ autonomous resolution rate (table-stakes by then)
- SOC 2 Type II report
- 3 customer case studies published with named logos
- 99.9% uptime

---

## Appendix A: Decision Log (key opinionated calls)

1. **AOPs replace Skills + Workflow Builder** — single abstraction for the spine.
2. **Postgres + pgvector for everything** — no ClickHouse, no separate vector DB, no Pinecone in MVP.
3. **Pub/Sub API + CDC for sync** — not CometD, not PushTopics, not pure polling.
4. **JWT Bearer per-org auth with dedicated integration user** — not per-user OAuth, not Client Credentials.
5. **Salesforce-wins conflict default with optimistic concurrency** — Heroku Connect's "DB wins" mode is a footgun.
6. **Watermark on SystemModstamp** — not LastModifiedDate.
7. **Claude Sonnet 4.5 default + Haiku triage + Opus escalation** — single-vendor primary with hybrid routing.
8. **LangGraph + Temporal** — durable, recoverable agent workflows are non-negotiable.
9. **Langfuse self-hosted** — observability as Day 1 dependency, not Q3 retrofit.
10. **Voyage embeddings + reranker** — ~10% better than OpenAI, worth the multi-vendor cost.
11. **assistant-ui + Vercel AI SDK 6 + SSE** — production chat infra without rebuilding.
12. **WorkOS AuthKit** — B2B SSO without Auth0's pricing chaos.
13. **Render → AWS migration path** — skip Kubernetes for 3 months.
14. **Citation-required mode is fail-closed** — hallucination defense is mandatory, not optional.
15. **Voice = transcripts only in MVP** — native voice is a v2 product.
16. **Design partner before Sprint 1** — synthetic demos don't sell anymore.