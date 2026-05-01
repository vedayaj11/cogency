"""Seed a 'refund_smoke' golden dataset with 4 cases that exercise the
case_manager AOP across the main decision branches:

1. Small in-policy refund — expect resolved with refund proposal.
2. Over-$500 refund — expect escalated_human (post-result guardrail).
3. Identity mismatch — expect halted on verify_customer_identity guardrail.
4. Subscription cancellation refund — expect prorated refund proposal.

Idempotent — re-running won't duplicate the dataset (uniqueness on
(tenant_id, name)) but DOES re-add cases. Drop the dataset first if you
want a clean reseed.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from db import async_session
from db.models.eval import GoldenCase, GoldenDataset

from app.config import get_settings  # type: ignore[import-not-found]


CASES = [
    {
        "tags": ["refund", "small", "in_policy"],
        "input_payload": {
            "case_id": "GOLD-001",
            "case_number": "GOLD-001",
            "subject": "Refund request — small overcharge ~$45",
            "description": (
                "I was charged $45 extra on my April invoice for two seats we "
                "removed in March. Please refund. Email on file: aisha.patel@example.com."
            ),
            "status": "New",
            "priority": "Low",
            "contact_id": "GOLD-CONTACT-001",
            "account_id": "GOLD-ACCT-001",
            "custom_fields": {"claimed_email": "aisha.patel@example.com"},
        },
        "expected_outcome": {
            "status": "resolved",
            "must_call": ["propose_refund"],
            "amount_usd_max": 50,
            "must_not_escalate": True,
            "rationale": "$45 is well under the $500 self-service ceiling; identity verifies; agent should propose refund and close.",
        },
    },
    {
        "tags": ["refund", "large", "escalation"],
        "input_payload": {
            "case_id": "GOLD-002",
            "case_number": "GOLD-002",
            "subject": "Refund request — enterprise plan, project cancelled",
            "description": (
                "We signed up for the $1,800 Enterprise annual plan in March but "
                "our project was cancelled. Requesting a full refund. Email on "
                "file: marcus.chen@example.com."
            ),
            "status": "Escalated",
            "priority": "High",
            "contact_id": "GOLD-CONTACT-002",
            "account_id": "GOLD-ACCT-002",
            "custom_fields": {"claimed_email": "marcus.chen@example.com"},
        },
        "expected_outcome": {
            "status": "escalated_human",
            "must_call": ["propose_refund"],
            "expected_guardrail": "refund_amount > 500",
            "rationale": "$1,800 trips the requires_approval_if guardrail; agent should propose then halt to inbox.",
        },
    },
    {
        "tags": ["refund", "identity_failure"],
        "input_payload": {
            "case_id": "GOLD-003",
            "case_number": "GOLD-003",
            "subject": "Refund request — identity mismatch",
            "description": (
                "Hello, I need a refund of $120 for the last invoice. My email "
                "is wrong-email@example.com. Please process."
            ),
            "status": "New",
            "priority": "Medium",
            "contact_id": "GOLD-CONTACT-003",
            "account_id": "GOLD-ACCT-003",
            "custom_fields": {"claimed_email": "wrong-email@example.com"},
        },
        "expected_outcome": {
            "status": "failed",
            "expected_guardrail": "verify_customer_identity.verified == false",
            "must_not_call": ["propose_refund"],
            "rationale": "Identity verification will fail (claimed email won't match); halt_on guardrail should trip; no refund proposed.",
        },
    },
    {
        "tags": ["refund", "subscription_cancel", "in_policy"],
        "input_payload": {
            "case_id": "GOLD-004",
            "case_number": "GOLD-004",
            "subject": "Cancel subscription mid-cycle, refund unused portion",
            "description": (
                "I'd like to cancel my $99/month subscription effective today. "
                "Per policy I think I'm owed a prorated refund for the remaining "
                "20 of 30 days. Email: priya.ravi@example.com."
            ),
            "status": "New",
            "priority": "Medium",
            "contact_id": "GOLD-CONTACT-004",
            "account_id": "GOLD-ACCT-004",
            "custom_fields": {"claimed_email": "priya.ravi@example.com"},
        },
        "expected_outcome": {
            "status": "resolved",
            "must_call": ["lookup_knowledge", "propose_refund"],
            "amount_usd_target": 66,
            "rationale": "Prorated refund per policy: (20/30) * $99 = $66. Agent should cite the cancelled-subscription clause from the refund policy KB.",
        },
    },
]


async def main() -> None:
    settings = get_settings()
    tenant_id: UUID = settings.cogency_dev_tenant_id

    async with async_session(settings.database_url) as session:
        existing = (
            await session.execute(
                select(GoldenDataset).where(
                    GoldenDataset.tenant_id == tenant_id,
                    GoldenDataset.name == "refund_smoke",
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = GoldenDataset(
                tenant_id=tenant_id,
                name="refund_smoke",
                description="Smoke test for case_manager refund handling across small/large/identity-mismatch/cancel branches.",
                aop_name="case_manager",
            )
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            print(f"created dataset {existing.id}")
        else:
            print(f"dataset already exists: {existing.id}")

        # Idempotent-ish: skip cases that already match by case_id in input_payload.
        existing_cases = list(
            (
                await session.execute(
                    select(GoldenCase).where(GoldenCase.dataset_id == existing.id)
                )
            )
            .scalars()
            .all()
        )
        existing_ids = {
            (c.input_payload or {}).get("case_id") for c in existing_cases
        }

        added = 0
        for c in CASES:
            if c["input_payload"]["case_id"] in existing_ids:
                continue
            session.add(
                GoldenCase(
                    dataset_id=existing.id,
                    input_payload=c["input_payload"],
                    expected_outcome=c["expected_outcome"],
                    rubric=None,
                    tags=c["tags"],
                )
            )
            added += 1
        if added:
            await session.commit()
        print(f"added {added} new cases (skipped {len(CASES) - added} existing)")


if __name__ == "__main__":
    asyncio.run(main())
