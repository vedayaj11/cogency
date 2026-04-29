"""Seed a handful of demo cases + contacts into the local mirror.

For UI demo purposes only — bypasses the Salesforce sync layer entirely.
Idempotent: re-running upserts on (org_id, id).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from db import async_session
from db.models.sf import SfCase, SfContact

DEV_ORG = UUID("00000000-0000-0000-0000-000000000001")

NOW = datetime.now(tz=UTC)


CONTACTS = [
    {
        "id": "0033t000XXXXXXC0AAA",
        "first_name": "Aisha",
        "last_name": "Patel",
        "email": "aisha.patel@northwind.example",
        "account_id": "0013t000XXXXXXA0AAA",
    },
    {
        "id": "0033t000XXXXXXC1AAA",
        "first_name": "Marcus",
        "last_name": "Chen",
        "email": "marcus.chen@orbital.example",
        "account_id": "0013t000XXXXXXA1AAA",
    },
    {
        "id": "0033t000XXXXXXC2AAA",
        "first_name": "Priya",
        "last_name": "Ravi",
        "email": "priya.ravi@helio.example",
        "account_id": "0013t000XXXXXXA2AAA",
    },
]


CASES = [
    {
        "id": "5003t000XXXXXX01AAA",
        "case_number": "00001001",
        "subject": "Refund request — duplicate annual subscription charge",
        "description": (
            "Hi, I just realized my company was charged twice for the annual plan "
            "($420 each) on April 22. Could you refund one of the charges? "
            "Account email on file: aisha.patel@northwind.example."
        ),
        "status": "Working",
        "priority": "High",
        "origin": "Email",
        "contact_id": "0033t000XXXXXXC0AAA",
        "account_id": "0013t000XXXXXXA0AAA",
        "custom_fields": {"claimed_email": "aisha.patel@northwind.example"},
        "modstamp": NOW - timedelta(minutes=14),
    },
    {
        "id": "5003t000XXXXXX02AAA",
        "case_number": "00001002",
        "subject": "Refund request — enterprise plan, project cancelled",
        "description": (
            "We signed up for the $1,800 Enterprise plan in March but our project "
            "was cancelled this week. Requesting a full refund. The PO is "
            "attached in our last email."
        ),
        "status": "Escalated",
        "priority": "High",
        "origin": "Email",
        "contact_id": "0033t000XXXXXXC1AAA",
        "account_id": "0013t000XXXXXXA1AAA",
        "custom_fields": {"claimed_email": "marcus.chen@orbital.example"},
        "modstamp": NOW - timedelta(hours=2),
    },
    {
        "id": "5003t000XXXXXX03AAA",
        "case_number": "00001003",
        "subject": "Password reset — unable to log in after SSO migration",
        "description": (
            "After the SSO migration last week I can't log in. I tried the reset "
            "link but it goes to the old portal."
        ),
        "status": "New",
        "priority": "Medium",
        "origin": "Web",
        "contact_id": "0033t000XXXXXXC2AAA",
        "account_id": "0013t000XXXXXXA2AAA",
        "custom_fields": {},
        "modstamp": NOW - timedelta(hours=8),
    },
    {
        "id": "5003t000XXXXXX04AAA",
        "case_number": "00001004",
        "subject": "Refund request — small overcharge, ~$45",
        "description": (
            "Saw a $45 overcharge on the April invoice for two seats we removed "
            "in March. Please refund — claimed email is aisha.patel@northwind.example."
        ),
        "status": "New",
        "priority": "Low",
        "origin": "Email",
        "contact_id": "0033t000XXXXXXC0AAA",
        "account_id": "0013t000XXXXXXA0AAA",
        "custom_fields": {"claimed_email": "aisha.patel@northwind.example"},
        "modstamp": NOW - timedelta(days=1),
    },
    {
        "id": "5003t000XXXXXX05AAA",
        "case_number": "00001005",
        "subject": "Subscription change — downgrade Enterprise to Team",
        "description": "Please move us from Enterprise to Team starting next billing cycle.",
        "status": "Closed",
        "priority": "Low",
        "origin": "Email",
        "contact_id": "0033t000XXXXXXC1AAA",
        "account_id": "0013t000XXXXXXA1AAA",
        "custom_fields": {},
        "modstamp": NOW - timedelta(days=3),
    },
]


async def main() -> None:
    async with async_session() as session:
        # contacts first (FK target for case.contact_id is just a string, no FK,
        # but keeping data consistent).
        for c in CONTACTS:
            stmt = insert(SfContact).values(
                org_id=DEV_ORG,
                id=c["id"],
                first_name=c["first_name"],
                last_name=c["last_name"],
                name=f"{c['first_name']} {c['last_name']}",
                email=c["email"],
                account_id=c["account_id"],
                custom_fields={},
                system_modstamp=NOW,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["org_id", "id"],
                set_={
                    "first_name": stmt.excluded.first_name,
                    "last_name": stmt.excluded.last_name,
                    "name": stmt.excluded.name,
                    "email": stmt.excluded.email,
                    "account_id": stmt.excluded.account_id,
                    "system_modstamp": stmt.excluded.system_modstamp,
                },
            )
            await session.execute(stmt)

        for c in CASES:
            stmt = insert(SfCase).values(
                org_id=DEV_ORG,
                id=c["id"],
                case_number=c["case_number"],
                subject=c["subject"],
                description=c["description"],
                status=c["status"],
                priority=c["priority"],
                origin=c["origin"],
                contact_id=c["contact_id"],
                account_id=c["account_id"],
                custom_fields=c["custom_fields"],
                created_date=c["modstamp"] - timedelta(hours=1),
                system_modstamp=c["modstamp"],
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["org_id", "id"],
                set_={
                    "subject": stmt.excluded.subject,
                    "description": stmt.excluded.description,
                    "status": stmt.excluded.status,
                    "priority": stmt.excluded.priority,
                    "origin": stmt.excluded.origin,
                    "contact_id": stmt.excluded.contact_id,
                    "account_id": stmt.excluded.account_id,
                    "custom_fields": stmt.excluded.custom_fields,
                    "system_modstamp": stmt.excluded.system_modstamp,
                },
            )
            await session.execute(stmt)
        await session.commit()
    print(f"seeded {len(CONTACTS)} contacts, {len(CASES)} cases.")


if __name__ == "__main__":
    asyncio.run(main())
