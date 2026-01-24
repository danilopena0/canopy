#!/usr/bin/env python3
"""Quick script to fetch job details for Claude Code to read."""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import Database
from src.config import get_settings


async def get_job(job_id: str) -> None:
    """Fetch and print job details."""
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if not row:
        print(f"Job not found: {job_id}")
        return

    job = dict(row)
    print(f"# {job['title']} at {job['company']}\n")
    print(f"**Location:** {job.get('location', 'Not specified')}")
    print(f"**Work Type:** {job.get('work_type', 'Not specified')}")
    if job.get('salary_min') or job.get('salary_max'):
        salary = f"${job.get('salary_min', 'N/A'):,} - ${job.get('salary_max', 'N/A'):,}"
        print(f"**Salary:** {salary}")
    print(f"**Source:** {job['source']}")
    print(f"**URL:** {job['url']}\n")

    if job.get('description'):
        print("## Description\n")
        print(job['description'])
        print()

    if job.get('requirements'):
        print("## Requirements\n")
        print(job['requirements'])

    await db.disconnect()


async def list_recent_jobs(limit: int = 10) -> None:
    """List recent jobs."""
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    rows = await db.fetchall(
        "SELECT id, title, company, source FROM jobs ORDER BY scraped_at DESC LIMIT ?",
        (limit,)
    )

    print("Recent Jobs:\n")
    for row in rows:
        print(f"  {row['id'][:8]}  {row['title'][:40]:<40}  {row['company'][:20]}")

    await db.disconnect()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_job.py <job_id>")
        print("       python get_job.py --list [limit]")
        sys.exit(1)

    if sys.argv[1] == "--list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        asyncio.run(list_recent_jobs(limit))
    else:
        asyncio.run(get_job(sys.argv[1]))
