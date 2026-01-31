"""Search routes for batch job searches and source management."""

import logging
import time
from typing import Annotated

from litestar import Controller, get, post
from litestar.di import Provide
from litestar.params import Parameter

from ..db import Database, db_dependency
from ..models import (
    CompanySource,
    CompanySourceCreate,
    SearchRun,
)
from ..scrapers import HEBScraper, IndeedScraper, WellfoundScraper
from ..services.scorer import ScorerService
from ..utils.dedup import generate_dedup_key, is_similar_title, normalize_company

logger = logging.getLogger(__name__)


class SearchRunResult:
    """Result of a search run."""

    def __init__(
        self,
        jobs_found: int = 0,
        new_jobs: int = 0,
        sources: str = "",
        duration_seconds: float = 0.0,
        message: str = "",
    ):
        self.jobs_found = jobs_found
        self.new_jobs = new_jobs
        self.sources = sources
        self.duration_seconds = duration_seconds
        self.message = message


class SearchController(Controller):
    """Controller for search-related endpoints."""

    path = "/api/search"
    dependencies = {"db": Provide(db_dependency)}

    async def _save_job(self, db: Database, job, skip_duplicates: bool = True) -> bool:
        """Save a job to the database. Returns True if it's a new job.

        Args:
            db: Database connection
            job: Job object to save
            skip_duplicates: If True, skip saving cross-source duplicates.
                             If False, save but mark as duplicate_of.
        """
        # Check if exact same job (same URL hash) exists
        existing = await db.fetchone(
            "SELECT id FROM jobs WHERE id = ?", (job.id,)
        )

        if existing:
            await db.execute(
                "UPDATE jobs SET scraped_at = CURRENT_TIMESTAMP WHERE id = ?",
                (job.id,),
            )
            logger.debug(f"Job already exists, updated timestamp: {job.id}")
            return False

        # Generate dedup key for cross-source duplicate detection
        dedup_key = generate_dedup_key(job.title, job.company, job.location)

        # Check for cross-source duplicates (same job from different source)
        duplicate_of = None
        existing_similar = await db.fetchall(
            """
            SELECT id, title, company, source FROM jobs
            WHERE dedup_key = ? AND source != ?
            """,
            (dedup_key, job.source),
        )

        if existing_similar:
            # Found potential duplicate(s) with same dedup_key
            for row in existing_similar:
                # Verify with title similarity check (dedup_key might have collisions)
                if is_similar_title(job.title, row["title"], threshold=0.85):
                    duplicate_of = row["id"]
                    logger.info(
                        f"Found cross-source duplicate: '{job.title}' at {job.company} "
                        f"(new: {job.source}, existing: {row['source']})"
                    )
                    if skip_duplicates:
                        # Update the original job's timestamp and skip
                        await db.execute(
                            "UPDATE jobs SET scraped_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (duplicate_of,),
                        )
                        return False
                    break

        # Also check for fuzzy matches without exact dedup_key (catches variations)
        if not duplicate_of:
            norm_company = normalize_company(job.company)
            # Get recent jobs from same company for fuzzy matching
            company_jobs = await db.fetchall(
                """
                SELECT id, title, company, source FROM jobs
                WHERE company LIKE ? AND source != ?
                ORDER BY scraped_at DESC LIMIT 50
                """,
                (f"%{norm_company[:20]}%", job.source),
            )
            for row in company_jobs:
                if normalize_company(row["company"]) == norm_company:
                    if is_similar_title(job.title, row["title"], threshold=0.90):
                        duplicate_of = row["id"]
                        logger.info(
                            f"Found fuzzy duplicate: '{job.title}' at {job.company} "
                            f"(matches '{row['title']}' from {row['source']})"
                        )
                        if skip_duplicates:
                            await db.execute(
                                "UPDATE jobs SET scraped_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (duplicate_of,),
                            )
                            return False
                        break

        # Insert the new job
        await db.execute(
            """
            INSERT INTO jobs (id, url, source, title, company, location, work_type,
                            salary_min, salary_max, description, requirements, posted_date,
                            dedup_key, duplicate_of)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.url,
                job.source,
                job.title,
                job.company,
                job.location,
                job.work_type,
                job.salary_min,
                job.salary_max,
                job.description,
                job.requirements,
                job.posted_date,
                dedup_key,
                duplicate_of,
            ),
        )
        if duplicate_of:
            logger.info(f"Added duplicate job: {job.title} at {job.company} (duplicate_of: {duplicate_of})")
        else:
            logger.info(f"Added new job: {job.title} at {job.company}")
        return True

    @post("/run")
    async def run_search(
        self,
        db: Database,
        location: Annotated[str, Parameter(query="location")] = "San Antonio, TX",
        keywords: Annotated[str, Parameter(query="keywords")] = "data scientist",
        sources_param: Annotated[str, Parameter(query="sources")] = "heb,indeed,wellfound",
        max_pages: Annotated[int, Parameter(query="max_pages", ge=1, le=10)] = 3,
        auto_score: Annotated[bool, Parameter(query="auto_score")] = True,
    ) -> dict:
        """Trigger a batch search across enabled sources.

        Args:
            location: Location to search for jobs. Defaults to San Antonio, TX.
            keywords: Keywords/query for job search. Defaults to "data scientist".
            sources_param: Comma-separated list of sources to scrape (heb, indeed, wellfound).
            max_pages: Max pages to scrape from Indeed (1-10). Defaults to 3.
            auto_score: Automatically score new jobs against profile. Defaults to True.

        Returns:
            Summary of the search run including jobs found and new jobs added.
        """
        start_time = time.time()
        jobs_found = 0
        new_jobs = 0
        new_job_ids = []  # Track new job IDs for scoring
        sources = [s.strip().lower() for s in sources_param.split(",") if s.strip()]
        errors = []

        logger.info(f"Starting job search: location={location}, keywords={keywords}, sources={sources}")

        # Run H-E-B scraper
        if "heb" in sources:
            try:
                logger.info("Running H-E-B scraper...")
                scraper = HEBScraper(location=location, keywords=keywords)
                async for job in scraper.scrape():
                    jobs_found += 1
                    if await self._save_job(db, job):
                        new_jobs += 1
                        new_job_ids.append(job.id)
                await db.commit()
            except Exception as e:
                logger.error(f"H-E-B scraper error: {e}")
                errors.append(f"heb: {str(e)}")

        # Run Indeed scraper
        if "indeed" in sources:
            try:
                logger.info("Running Indeed scraper...")
                scraper = IndeedScraper(
                    query=keywords,
                    location=location,
                    radius=50,
                    days_ago=7,
                    max_pages=max_pages,
                )
                async for job in scraper.scrape():
                    jobs_found += 1
                    if await self._save_job(db, job):
                        new_jobs += 1
                        new_job_ids.append(job.id)
                await db.commit()
            except Exception as e:
                logger.error(f"Indeed scraper error: {e}")
                errors.append(f"indeed: {str(e)}")

        # Run Wellfound scraper
        if "wellfound" in sources:
            try:
                logger.info("Running Wellfound scraper...")
                # Map keywords to role slug
                role_map = {
                    "data scientist": "data-scientist",
                    "machine learning": "machine-learning-engineer",
                    "ml engineer": "machine-learning-engineer",
                    "data engineer": "data-engineer",
                    "ai engineer": "ai-engineer",
                }
                role = role_map.get(keywords.lower(), "data-scientist")
                scraper = WellfoundScraper(
                    role=role,
                    max_pages=max_pages,
                )
                async for job in scraper.scrape():
                    jobs_found += 1
                    if await self._save_job(db, job):
                        new_jobs += 1
                        new_job_ids.append(job.id)
                await db.commit()
            except Exception as e:
                logger.error(f"Wellfound scraper error: {e}")
                errors.append(f"wellfound: {str(e)}")

        # Auto-score new jobs if enabled
        scored_jobs = 0
        if auto_score and new_job_ids:
            try:
                logger.info(f"Auto-scoring {len(new_job_ids)} new jobs...")
                scorer = ScorerService()
                try:
                    profile = scorer.load_profile()
                    for job_id in new_job_ids:
                        row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
                        if row:
                            job_dict = dict(row)
                            result = await scorer.score_job(job_dict, profile)
                            await db.execute(
                                "UPDATE jobs SET fit_score = ?, fit_rationale = ? WHERE id = ?",
                                (result["score"], result["rationale"], job_id),
                            )
                            scored_jobs += 1
                            logger.info(f"Scored {job_dict['title']}: {result['score']}/100")
                    await db.commit()
                except FileNotFoundError:
                    logger.warning("Profile not found, skipping auto-score")
                finally:
                    await scorer.close()
            except Exception as e:
                logger.error(f"Auto-scoring error: {e}")
                errors.append(f"scoring: {str(e)}")

        duration = time.time() - start_time

        # Record the search run
        await db.execute(
            """
            INSERT INTO search_runs (sources, jobs_found, new_jobs, duration_seconds)
            VALUES (?, ?, ?, ?)
            """,
            (",".join(sources), jobs_found, new_jobs, duration),
        )
        await db.commit()

        message = f"Search complete. Found {jobs_found} jobs, {new_jobs} new."
        if scored_jobs:
            message += f" Scored {scored_jobs} jobs."
        if errors:
            message += f" Errors: {'; '.join(errors)}"

        logger.info(f"{message} Duration: {duration:.2f}s")

        return {
            "message": message,
            "jobs_found": jobs_found,
            "new_jobs": new_jobs,
            "scored_jobs": scored_jobs,
            "sources": sources,
            "duration_seconds": round(duration, 2),
            "errors": errors if errors else None,
        }

    @get("/runs")
    async def list_search_runs(
        self,
        db: Database,
        limit: Annotated[int, Parameter(query="limit", ge=1, le=100)] = 20,
    ) -> list[SearchRun]:
        """List past search runs."""
        rows = await db.fetchall(
            "SELECT * FROM search_runs ORDER BY run_at DESC LIMIT ?",
            (limit,),
        )
        return [SearchRun(**dict(row)) for row in rows]

    @get("/sources")
    async def list_sources(self, db: Database) -> list[CompanySource]:
        """List configured job sources."""
        rows = await db.fetchall(
            "SELECT * FROM company_sources ORDER BY company_name"
        )
        return [CompanySource(**dict(row)) for row in rows]

    @post("/sources")
    async def add_source(
        self, db: Database, data: CompanySourceCreate
    ) -> CompanySource:
        """Add a new job source."""
        cursor = await db.execute(
            """
            INSERT INTO company_sources (company_name, careers_url, scrape_config, category)
            VALUES (?, ?, ?, ?)
            """,
            (
                data.company_name,
                data.careers_url,
                data.scrape_config,
                data.category,
            ),
        )
        await db.commit()

        row = await db.fetchone(
            "SELECT * FROM company_sources WHERE id = ?",
            (cursor.lastrowid,),
        )
        return CompanySource(**dict(row))

    @post("/backfill-dedup")
    async def backfill_dedup_keys(self, db: Database) -> dict:
        """Backfill dedup_keys for existing jobs that don't have one.

        This is a one-time operation to add dedup_keys to jobs that were
        scraped before the dedup feature was added.
        """
        # Get jobs without dedup_key
        rows = await db.fetchall(
            "SELECT id, title, company, location FROM jobs WHERE dedup_key IS NULL"
        )

        updated = 0
        for row in rows:
            dedup_key = generate_dedup_key(row["title"], row["company"], row["location"])
            await db.execute(
                "UPDATE jobs SET dedup_key = ? WHERE id = ?",
                (dedup_key, row["id"]),
            )
            updated += 1

        await db.commit()
        logger.info(f"Backfilled dedup_keys for {updated} jobs")

        return {"message": f"Backfilled {updated} jobs with dedup_keys"}

    @get("/duplicates")
    async def find_duplicates(
        self,
        db: Database,
        threshold: Annotated[float, Parameter(query="threshold", ge=0.5, le=1.0)] = 0.85,
    ) -> dict:
        """Find potential duplicate jobs in the database.

        Returns groups of jobs that might be duplicates based on normalized
        title and company matching.
        """
        # Get all jobs with dedup_key
        rows = await db.fetchall(
            """
            SELECT id, title, company, source, location, scraped_at, dedup_key
            FROM jobs
            WHERE status != 'archived' AND duplicate_of IS NULL
            ORDER BY company, title
            """
        )

        # Group by dedup_key
        from collections import defaultdict
        groups = defaultdict(list)
        for row in rows:
            key = row["dedup_key"]
            if key:
                groups[key].append(dict(row))

        # Filter to groups with more than one job
        duplicate_groups = [
            {"dedup_key": key, "jobs": jobs}
            for key, jobs in groups.items()
            if len(jobs) > 1
        ]

        # Also find fuzzy matches that might have different dedup_keys
        fuzzy_duplicates = []
        jobs_list = list(rows)
        seen_pairs = set()

        for i, job1 in enumerate(jobs_list):
            for job2 in jobs_list[i + 1:]:
                if job1["id"] == job2["id"]:
                    continue

                # Skip if already in a dedup_key group
                if job1["dedup_key"] == job2["dedup_key"] and job1["dedup_key"]:
                    continue

                # Check if same company (normalized)
                if normalize_company(job1["company"]) != normalize_company(job2["company"]):
                    continue

                # Check title similarity
                if is_similar_title(job1["title"], job2["title"], threshold):
                    pair_key = tuple(sorted([job1["id"], job2["id"]]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        fuzzy_duplicates.append({
                            "job1": dict(job1),
                            "job2": dict(job2),
                        })

        return {
            "exact_matches": duplicate_groups,
            "exact_match_count": len(duplicate_groups),
            "fuzzy_matches": fuzzy_duplicates[:50],  # Limit to 50
            "fuzzy_match_count": len(fuzzy_duplicates),
        }
