#!/usr/bin/env python3
"""Run scrapers and surface the top new jobs ranked by fit score.

Usage:
    python scripts/hunt_jobs.py                          # Default: all sources, top 15
    python scripts/hunt_jobs.py --sources indeed,wellfound
    python scripts/hunt_jobs.py --keywords "ML engineer" --min-score 60
    python scripts/hunt_jobs.py --limit 20 --all         # Include already-seen jobs
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

BASE_URL = "http://localhost:8000"


async def run_search(sources: str, keywords: str, max_pages: int) -> dict:
    async with httpx.AsyncClient(timeout=300) as client:
        params = {"sources": sources, "keywords": keywords, "max_pages": max_pages}
        resp = await client.post(f"{BASE_URL}/api/search/run", params=params)
        resp.raise_for_status()
        return resp.json()


async def get_top_jobs(min_score: float, limit: int, include_seen: bool) -> list[dict]:
    from src.db import Database
    from src.config import get_settings

    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    status_filter = "" if include_seen else "AND status = 'new'"
    rows = await db.fetchall(
        f"""
        SELECT id, title, company, location, work_type, fit_score, fit_rationale,
               salary_min, salary_max, source, url, scraped_at
        FROM jobs
        WHERE fit_score >= ? AND duplicate_of IS NULL {status_filter}
        ORDER BY fit_score DESC
        LIMIT ?
        """,
        (min_score, limit),
    )
    await db.disconnect()
    return [dict(r) for r in rows]


def fmt_salary(mn, mx):
    if mn and mx:
        return f"${mn:,}–${mx:,}"
    if mn:
        return f"${mn:,}+"
    if mx:
        return f"up to ${mx:,}"
    return "not listed"


async def main():
    parser = argparse.ArgumentParser(description="Hunt for new jobs")
    parser.add_argument("--sources", default="heb,indeed,wellfound")
    parser.add_argument("--keywords", default="data scientist")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=50)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--no-scrape", action="store_true", help="Skip scraping, just query DB")
    parser.add_argument("--all", action="store_true", help="Include jobs already shortlisted/applied")
    args = parser.parse_args()

    if not args.no_scrape:
        print(f"Running scrapers: {args.sources} | keywords: '{args.keywords}'")
        print("This may take 1-3 minutes...\n")
        try:
            result = await run_search(args.sources, args.keywords, args.max_pages)
            print(f"Scrape complete: {result.get('new_jobs', 0)} new jobs found ({result.get('jobs_found', 0)} total)")
            print()
        except Exception as e:
            print(f"Warning: scraper failed ({e}). Showing existing DB results.\n")

    jobs = await get_top_jobs(args.min_score, args.limit, args.all)

    if not jobs:
        print(f"No jobs found with fit_score >= {args.min_score}.")
        return

    print(f"Top {len(jobs)} jobs (score >= {args.min_score}):\n")
    print(f"{'#':<3} {'Score':<7} {'Title':<38} {'Company':<22} {'Type':<10} {'Salary'}")
    print("-" * 105)
    for i, job in enumerate(jobs, 1):
        score = f"{job['fit_score']:.0f}/100" if job["fit_score"] else "unscored"
        title = (job["title"] or "")[:37]
        company = (job["company"] or "")[:21]
        wtype = (job["work_type"] or "?")[:9]
        salary = fmt_salary(job["salary_min"], job["salary_max"])
        print(f"{i:<3} {score:<7} {title:<38} {company:<22} {wtype:<10} {salary}")
        print(f"    ID: {job['id']}  |  {job['source']}  |  {job['url'][:60]}")
        if job.get("fit_rationale"):
            rationale_short = job["fit_rationale"][:120].replace("\n", " ")
            print(f"    {rationale_short}...")
        print()


if __name__ == "__main__":
    asyncio.run(main())
