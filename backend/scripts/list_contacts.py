#!/usr/bin/env python3
"""List and query contacts in the networking database.

Usage:
    python scripts/list_contacts.py                     # All contacts
    python scripts/list_contacts.py --company USAA      # Filter by company
    python scripts/list_contacts.py --id 3              # Show contact + their outreach history
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import Database
from src.config import get_settings


async def list_contacts(company: str | None = None) -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    if company:
        rows = await db.fetchall(
            "SELECT * FROM contacts WHERE LOWER(company) LIKE ? ORDER BY company, name",
            (f"%{company.lower()}%",),
        )
    else:
        rows = await db.fetchall("SELECT * FROM contacts ORDER BY company, name")

    if not rows:
        print("No contacts found.")
        await db.disconnect()
        return

    print(f"{'ID':<5} {'Name':<25} {'Company':<22} {'Role':<28} {'Met via'}")
    print("-" * 95)
    for row in rows:
        c = dict(row)
        met = (c.get("met_via") or "")[:20]
        role = (c.get("role") or "")[:27]
        print(f"{c['id']:<5} {c['name']:<25} {c['company']:<22} {role:<28} {met}")

    await db.disconnect()


async def show_contact(contact_id: int) -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    row = await db.fetchone("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    if not row:
        print(f"Contact not found: {contact_id}")
        await db.disconnect()
        return

    c = dict(row)
    print(f"\n# {c['name']} @ {c['company']}")
    if c.get("role"):
        print(f"Role:     {c['role']}")
    if c.get("linkedin_url"):
        print(f"LinkedIn: {c['linkedin_url']}")
    if c.get("met_via"):
        print(f"Met via:  {c['met_via']}")
    if c.get("notes"):
        print(f"Notes:    {c['notes']}")
    if c.get("last_contact_at"):
        print(f"Last contact: {c['last_contact_at']}")

    # Show outreach history
    outreach = await db.fetchall(
        """
        SELECT n.*, j.title as job_title, j.company as job_company
        FROM networking n
        LEFT JOIN jobs j ON n.job_id = j.id
        WHERE n.contact_id = ?
        ORDER BY n.created_at DESC
        """,
        (contact_id,),
    )

    if outreach:
        print(f"\n## Outreach history ({len(outreach)} records)")
        for o in outreach:
            o = dict(o)
            job_ref = f" → {o['job_title']} @ {o['job_company']}" if o.get("job_title") else ""
            print(f"  [{o['status'].upper()}] {o['type']}{job_ref}")
            if o.get("notes"):
                print(f"    {o['notes']}")
            if o.get("follow_up_at"):
                print(f"    Follow up: {o['follow_up_at']}")
    else:
        print("\nNo outreach recorded yet.")

    await db.disconnect()


def main():
    parser = argparse.ArgumentParser(description="List contacts in the networking DB")
    parser.add_argument("--company", help="Filter by company name (partial match)")
    parser.add_argument("--id", type=int, dest="contact_id", help="Show details for a specific contact ID")
    args = parser.parse_args()

    if args.contact_id:
        asyncio.run(show_contact(args.contact_id))
    else:
        asyncio.run(list_contacts(args.company))


if __name__ == "__main__":
    main()
