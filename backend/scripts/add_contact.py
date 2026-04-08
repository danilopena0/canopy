#!/usr/bin/env python3
"""Add a contact to the networking database.

Usage:
    python scripts/add_contact.py "Jane Smith" "USAA" --role "Sr Data Scientist" --linkedin "https://linkedin.com/in/janesmith" --met-via "LinkedIn search"
    python scripts/add_contact.py "Bob Jones" "HEB" --notes "Met at SA tech meetup"
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import Database
from src.config import get_settings


async def add_contact(name: str, company: str, role: str | None, linkedin_url: str | None,
                      met_via: str | None, notes: str | None) -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    cursor = await db.execute(
        """
        INSERT INTO contacts (name, company, role, linkedin_url, met_via, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, company, role, linkedin_url, met_via, notes),
    )
    await db.commit()
    contact_id = cursor.lastrowid
    await db.disconnect()

    print(f"Contact added (ID: {contact_id})")
    print(f"  Name:    {name}")
    print(f"  Company: {company}")
    if role:
        print(f"  Role:    {role}")
    if linkedin_url:
        print(f"  LinkedIn: {linkedin_url}")
    if met_via:
        print(f"  Met via: {met_via}")
    if notes:
        print(f"  Notes:   {notes}")


def main():
    parser = argparse.ArgumentParser(description="Add a contact to the networking DB")
    parser.add_argument("name", help="Contact's full name")
    parser.add_argument("company", help="Company they work at")
    parser.add_argument("--role", help="Their job title/role")
    parser.add_argument("--linkedin", dest="linkedin_url", help="LinkedIn profile URL")
    parser.add_argument("--met-via", help="How you found/met them (e.g. 'LinkedIn search', 'SA meetup')")
    parser.add_argument("--notes", help="Any notes about this contact")
    args = parser.parse_args()

    asyncio.run(add_contact(args.name, args.company, args.role, args.linkedin_url, args.met_via, args.notes))


if __name__ == "__main__":
    main()
