#!/usr/bin/env python3
"""Seed the database with initial company sources."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_database

# Initial company sources for San Antonio / Austin area
INITIAL_SOURCES = [
    # Defense Contractors
    {"company_name": "USAA", "careers_url": "https://www.usaa.com/careers", "category": "defense"},
    {"company_name": "Booz Allen Hamilton", "careers_url": "https://www.boozallen.com/careers.html", "category": "defense"},
    {"company_name": "CACI", "careers_url": "https://careers.caci.com/", "category": "defense"},
    {"company_name": "Leidos", "careers_url": "https://careers.leidos.com/", "category": "defense"},
    {"company_name": "General Dynamics IT", "careers_url": "https://www.gd.com/careers", "category": "defense"},
    {"company_name": "Lockheed Martin", "careers_url": "https://www.lockheedmartinjobs.com/", "category": "defense"},
    {"company_name": "Raytheon", "careers_url": "https://careers.rtx.com/", "category": "defense"},
    # Healthcare
    {"company_name": "Methodist Healthcare", "careers_url": "https://sahealth.com/careers/", "category": "healthcare"},
    {"company_name": "University Health", "careers_url": "https://www.universityhealthsystem.com/careers", "category": "healthcare"},
    # Financial Services
    {"company_name": "Frost Bank", "careers_url": "https://www.frostbank.com/careers", "category": "finance"},
    # Tech / Startups
    {"company_name": "Rackspace", "careers_url": "https://www.rackspace.com/about/careers", "category": "tech"},
    {"company_name": "data.world", "careers_url": "https://data.world/careers", "category": "tech"},
    {"company_name": "Indeed", "careers_url": "https://www.indeed.com/cmp/Indeed/jobs", "category": "tech"},
    {"company_name": "Oracle", "careers_url": "https://www.oracle.com/careers/", "category": "tech"},
    {"company_name": "Dell", "careers_url": "https://jobs.dell.com/", "category": "tech"},
    {"company_name": "Apple", "careers_url": "https://www.apple.com/careers/", "category": "tech"},
    {"company_name": "Meta", "careers_url": "https://www.metacareers.com/", "category": "tech"},
    {"company_name": "Google", "careers_url": "https://careers.google.com/", "category": "tech"},
    {"company_name": "Amazon", "careers_url": "https://www.amazon.jobs/", "category": "tech"},
]


async def seed_sources():
    """Insert initial company sources into the database."""
    db = await get_database()

    for source in INITIAL_SOURCES:
        try:
            await db.execute(
                """
                INSERT OR IGNORE INTO company_sources (company_name, careers_url, category)
                VALUES (?, ?, ?)
                """,
                (source["company_name"], source["careers_url"], source["category"]),
            )
        except Exception as e:
            print(f"Error inserting {source['company_name']}: {e}")

    await db.commit()
    print(f"Seeded {len(INITIAL_SOURCES)} company sources")


if __name__ == "__main__":
    asyncio.run(seed_sources())
