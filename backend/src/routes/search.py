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
from ..scrapers import HEBScraper

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

    @post("/run")
    async def run_search(
        self,
        db: Database,
        location: Annotated[str, Parameter(query="location")] = "San Antonio, TX",
        keywords: Annotated[str, Parameter(query="keywords")] = "data",
    ) -> dict:
        """Trigger a batch search across all enabled sources.

        Args:
            location: Location to search for jobs. Defaults to San Antonio, TX.
            keywords: Keywords to filter jobs. Defaults to "data".

        Returns:
            Summary of the search run including jobs found and new jobs added.
        """
        start_time = time.time()
        jobs_found = 0
        new_jobs = 0
        sources = ["heb"]

        logger.info(f"Starting job search for location: {location}, keywords: {keywords}")

        # Run H-E-B scraper
        scraper = HEBScraper(location=location, keywords=keywords)

        async for job in scraper.scrape():
            jobs_found += 1

            # Check if job already exists
            existing = await db.fetchone(
                "SELECT id FROM jobs WHERE id = ?", (job.id,)
            )

            if existing:
                # Update scraped_at timestamp
                await db.execute(
                    "UPDATE jobs SET scraped_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (job.id,),
                )
                logger.debug(f"Job already exists, updated timestamp: {job.id}")
            else:
                # Insert new job
                await db.execute(
                    """
                    INSERT INTO jobs (id, url, source, title, company, location, work_type,
                                    salary_min, salary_max, description, requirements, posted_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
                new_jobs += 1
                logger.info(f"Added new job: {job.title} at {job.company}")

        await db.commit()

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

        logger.info(
            f"Search complete. Found {jobs_found} jobs, {new_jobs} new. "
            f"Duration: {duration:.2f}s"
        )

        return {
            "message": f"Search complete. Found {jobs_found} jobs, {new_jobs} new.",
            "jobs_found": jobs_found,
            "new_jobs": new_jobs,
            "sources": sources,
            "duration_seconds": round(duration, 2),
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
