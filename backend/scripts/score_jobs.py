#!/usr/bin/env python
"""Score all unscored jobs in the database.

Usage:
    python scripts/score_jobs.py           # Score all unscored jobs
    python scripts/score_jobs.py --all     # Re-score all jobs (even scored ones)
    python scripts/score_jobs.py --limit 5 # Score only 5 jobs
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add backend directory to path so we can import src as a package
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db import Database
from src.services.scorer import ScorerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def score_jobs(rescore_all: bool = False, limit: int | None = None):
    """Score jobs in the database.

    Args:
        rescore_all: If True, re-score all jobs. If False, only unscored jobs.
        limit: Maximum number of jobs to score. None for all.
    """
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    # Build query
    if rescore_all:
        query = "SELECT * FROM jobs WHERE duplicate_of IS NULL"
    else:
        query = "SELECT * FROM jobs WHERE fit_score IS NULL AND duplicate_of IS NULL"

    if limit:
        query += f" LIMIT {limit}"

    rows = await db.fetchall(query)
    total = len(rows)

    if total == 0:
        logger.info("No jobs to score.")
        await db.disconnect()
        return

    logger.info(f"Scoring {total} jobs...")

    scorer = ScorerService()

    try:
        profile = scorer.load_profile()
    except FileNotFoundError as e:
        logger.error(str(e))
        await db.disconnect()
        return

    scored = 0
    failed = 0

    try:
        for i, row in enumerate(rows, 1):
            job = dict(row)
            job_id = job["id"]
            title = job["title"]
            company = job["company"]

            logger.info(f"[{i}/{total}] Scoring: {title} at {company}")

            try:
                result = await scorer.score_job(job, profile)

                await db.execute(
                    "UPDATE jobs SET fit_score = ?, fit_rationale = ? WHERE id = ?",
                    (result["score"], result["rationale"], job_id),
                )
                await db.commit()

                score = result["score"]
                logger.info(f"  → Score: {score}/100")

                if result["dealbreaker_triggered"]:
                    logger.info(f"  → Dealbreaker: {result['dealbreaker_triggered']}")

                scored += 1

            except Exception as e:
                logger.error(f"  → Failed: {e}")
                failed += 1

    finally:
        await scorer.close()
        await db.disconnect()

    logger.info(f"\nDone! Scored: {scored}, Failed: {failed}")


def main():
    parser = argparse.ArgumentParser(description="Score jobs against your profile")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Re-score all jobs, not just unscored ones"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of jobs to score"
    )
    args = parser.parse_args()

    asyncio.run(score_jobs(rescore_all=args.all, limit=args.limit))


if __name__ == "__main__":
    main()
