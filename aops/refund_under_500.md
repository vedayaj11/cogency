---
name: refund_under_500
description: Issue a refund of up to $500 USD on a single order, contingent on identity verification and a valid policy reason.
persona_id: support_brand_voice_v1
steps:
  - name: load_case
    tool: lookup_case
    required_scopes: [case.read]
    inputs:
      case_id: case.id
    outputs:
      subject: string
      description: string
      contact_id: string
  - name: verify_identity
    tool: verify_customer_identity
    required_scopes: [contact.read, case.read]
    inputs:
      case_id: case.id
      claimed_email: case.custom_fields.claimed_email
    outputs:
      verified: bool
    fallback: escalate
  - name: propose
    tool: propose_refund
    required_scopes: [refund.propose]
    inputs:
      case_id: case.id
      amount_usd: derived_from_description
      reason: derived_from_description
    outputs:
      requires_approval: bool
      amount_usd: number
  - name: write_comment
    tool: add_case_comment
    required_scopes: [case.update]
    inputs:
      case_id: case.id
      body: refund_summary
      is_public: false
  - name: close_case
    tool: update_case_status
    required_scopes: [case.update]
    inputs:
      case_id: case.id
      status: literal:Closed
guardrails:
  - kind: requires_approval_if
    expr: refund_amount > 500
    message: Refund exceeds the $500 self-service ceiling; route to a senior agent.
  - kind: halt_on
    expr: verify_customer_identity.verified == false
    message: Identity verification failed; do not process a refund.
---

# Refund (under $500)

You are processing a refund request on behalf of an enterprise CX team. Follow this procedure exactly:

1. **Load case context** — call `lookup_case` with the case_id from the user message. If the case is not found, emit a final message explaining the failure and stop.
2. **Verify the customer's identity** — call `verify_customer_identity` with `case_id` and the email the customer claimed. Pull the claimed email from the case description if present, otherwise from `custom_fields.claimed_email`. If `verified=false`, the runtime guardrail will halt — do not proceed.
3. **Determine the refund amount** — read the case description carefully and extract:
   - the dollar amount the customer is requesting (USD),
   - a one-sentence justification grounded in the case description.
4. **Propose the refund** — call `propose_refund` with the amount and reason. If `requires_approval=true` (i.e. amount > $500), the runtime will route the case to the Agent Inbox; do not attempt to bypass.
5. **Record the decision** — call `add_case_comment` with a concise (≤ 80 word) internal-only summary including: amount proposed, reason, identity verification result. `is_public=false`.
6. **Close the case** — call `update_case_status` with `status="Closed"` only if the refund proposal completed without escalation.
7. **Emit a final message** summarizing what you did. Do not invent customer details — every fact must trace to a tool result.

## Operating constraints
- Never call `propose_refund` more than once per run.
- Never propose a refund larger than the amount the customer requested.
- If any tool returns an error, surface it in the final message and stop.
- The runtime enforces the guardrails above; you do not need to check them manually.
