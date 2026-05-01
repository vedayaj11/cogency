# Refund Policy — Customer Support Reference

This is the canonical reference for refund handling decisions made by Cogency's case management agents. When a refund question arises, agents MUST cite the relevant section before issuing a refund proposal.

## Eligibility windows

Customers are eligible for a full refund within **30 days** of the original transaction. Partial refunds (prorated by usage) are available between 30 and 60 days. After 60 days, refunds are not granted except in exceptional circumstances (see the *Exception path* below).

## Self-service ceiling

Support agents — human or AI — may self-approve refunds **up to $500**. Refunds above $500 require approval from a senior agent or a CX manager. The runtime guardrail enforces this automatically: any `propose_refund` with `amount_usd > 500` halts the run and routes the proposed action to the Agent Inbox.

## Identity verification requirement

Before any refund is issued, the requester's identity MUST be verified. The `verify_customer_identity` tool compares the email address claimed in the case against the email on file for the related Contact. If the emails do not match exactly (case-insensitive, trimmed), the refund must be denied or the case escalated.

## Duplicate charges

Duplicate charges within a single billing cycle are refunded automatically — no escalation, no approval. The agent should:

1. Confirm the duplicate via the customer's transaction history.
2. Refund the redundant charge in full.
3. Add a public case comment confirming the refund and apologizing for the inconvenience.
4. Close the case with status "Closed".

## Cancelled subscriptions

If the customer cancels their subscription mid-cycle, they are entitled to a prorated refund for the unused portion. The proration is calculated as: `(remaining_days / billing_cycle_days) * subscription_price`. Round to the nearest cent.

## Exception path (over 60 days, over $500, or both)

For requests outside the standard windows or above the self-service ceiling, the agent should:

1. Document the exception reason in a non-public case comment.
2. Use `create_escalation` to route the case to the CX manager queue with a clear justification.
3. Add a customer-facing comment explaining that a senior team member will follow up within 24 hours.

## What NOT to do

- Do not issue a refund without identity verification.
- Do not issue partial refunds without documenting the proration calculation.
- Do not close a case with an unresolved customer question pending — always reply first.
- Do not chain refund requests across multiple cases for the same incident; mark them as duplicates instead.
