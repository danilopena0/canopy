#!/usr/bin/env python3
"""Ingest a single job URL into the database.

Usage:
    python scripts/ingest_job.py <url>
    python scripts/ingest_job.py <url> --score   # also run fit scoring
    python scripts/ingest_job.py <url> --dry-run  # parse only, don't save
"""

import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db import Database
from src.services.llm import get_llm_provider

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

PARSE_SYSTEM_PROMPT = """You are a job posting parser. Extract structured data from raw job posting text.
Be thorough — capture all requirements, responsibilities, and qualifications."""

PARSE_USER_PROMPT = """Parse this job posting into structured data.

URL: {url}

Raw content:
{content}

Extract and return JSON with these fields:
{{
  "title": "exact job title",
  "company": "company name",
  "location": "city, state or 'Remote' or 'Hybrid'",
  "work_type": "remote|hybrid|onsite|null",
  "salary_min": null or integer annual,
  "salary_max": null or integer annual,
  "description": "full job description / responsibilities section",
  "requirements": "full requirements / qualifications section",
  "posted_date": "YYYY-MM-DD or null"
}}

For work_type: use "remote" if fully remote, "hybrid" if hybrid, "onsite" if in-office only, null if unclear.
For salary: convert hourly to annual (x2080), monthly to annual (x12). Use null if not mentioned.
Preserve the full text of description and requirements — do not summarize."""


async def scrape_url(url: str) -> str:
    """Fetch page content using crawl4ai."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(
            word_count_threshold=50,
            remove_overlay_elements=True,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            if result.success:
                return result.markdown or result.cleaned_html or ""
            else:
                logger.error(f"Crawl failed: {result.error_message}")
                return ""
    except ImportError:
        print("crawl4ai not installed. Install with: pip install crawl4ai")
        sys.exit(1)


async def parse_job(url: str, content: str, llm) -> dict:
    """Use LLM to parse raw page content into structured job data."""
    # Truncate very long content to avoid token limits
    if len(content) > 12000:
        content = content[:12000] + "\n\n[content truncated]"

    prompt = PARSE_USER_PROMPT.format(url=url, content=content)
    result = await llm.complete_json(prompt, PARSE_SYSTEM_PROMPT)
    return result


def generate_job_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


async def ingest(url: str, score: bool = False, dry_run: bool = False) -> str | None:
    """Ingest a job URL. Returns job_id on success."""
    settings = get_settings()

    print(f"Fetching: {url}")
    content = await scrape_url(url)

    if not content:
        print("ERROR: Could not fetch page content.")
        return None

    print("Parsing job data with LLM...")
    llm = get_llm_provider()
    try:
        job_data = await parse_job(url, content, llm)
    finally:
        await llm.close()

    # Validate we got required fields
    if not job_data.get("title") or not job_data.get("company"):
        print("ERROR: Could not extract job title or company from page.")
        print("Raw parse result:", json.dumps(job_data, indent=2))
        return None

    job_id = generate_job_id(url)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Job ID:   {job_id}")
    print(f"Title:    {job_data.get('title')}")
    print(f"Company:  {job_data.get('company')}")
    print(f"Location: {job_data.get('location', 'Not specified')}")
    print(f"Type:     {job_data.get('work_type', 'Not specified')}")
    if job_data.get("salary_min") or job_data.get("salary_max"):
        lo = job_data.get("salary_min")
        hi = job_data.get("salary_max")
        if lo and hi and lo != hi:
            print(f"Salary:   ${lo:,} - ${hi:,}")
        else:
            print(f"Salary:   ${(lo or hi):,}")
    print(f"{'='*60}\n")

    if dry_run:
        print("[Dry run — not saving to database]")
        print("\nDescription preview:")
        desc = job_data.get("description", "")
        print(desc[:500] + ("..." if len(desc) > 500 else ""))
        return job_id

    # Save to database
    db = Database(settings.database_path)
    await db.connect()

    try:
        # Check if already exists
        existing = await db.fetchone("SELECT id FROM jobs WHERE id = ?", (job_id,))
        if existing:
            print(f"Job already exists in database (id: {job_id})")
        else:
            await db.execute(
                """INSERT INTO jobs
                   (id, url, source, title, company, location, work_type,
                    salary_min, salary_max, description, requirements, posted_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    url,
                    "manual",
                    job_data.get("title"),
                    job_data.get("company"),
                    job_data.get("location"),
                    job_data.get("work_type"),
                    job_data.get("salary_min"),
                    job_data.get("salary_max"),
                    job_data.get("description"),
                    job_data.get("requirements"),
                    job_data.get("posted_date"),
                ),
            )
            print(f"Saved to database.")

        if score:
            print("Scoring job fit...")
            from src.services.scorer import ScorerService
            scorer = ScorerService()
            row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if row:
                job_dict = dict(row)
                score_result = await scorer.score_job(job_dict)
                await db.execute(
                    "UPDATE jobs SET fit_score = ?, fit_rationale = ? WHERE id = ?",
                    (score_result.get("score"), json.dumps(score_result), job_id),
                )
                fit = score_result.get("score", 0)
                print(f"Fit score: {fit}/100")
                if score_result.get("dealbreaker_triggered"):
                    print("  ⚠ Dealbreaker triggered")
            await scorer.close()

    finally:
        await db.disconnect()

    print(f"\nDone. Job ID: {job_id}")
    print(f"Run application agents with:")
    print(f"  python scripts/build_application.py {job_id}")
    print(f"  python scripts/interview_prep.py {job_id}")
    return job_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_job.py <url> [--score] [--dry-run]")
        sys.exit(1)

    url = sys.argv[1]
    do_score = "--score" in sys.argv
    dry_run = "--dry-run" in sys.argv

    asyncio.run(ingest(url, score=do_score, dry_run=dry_run))
