"""Job routes for CRUD operations and search."""

import hashlib
from typing import Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter

from ..db import Database, db_dependency
from ..models import (
    Job,
    JobCreate,
    JobFilterParams,
    JobList,
    JobStatus,
    JobUpdate,
    MessageResponse,
    SearchParams,
    WorkType,
)


def generate_job_id(url: str) -> str:
    """Generate a stable job ID from the URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class JobController(Controller):
    """Controller for job-related endpoints."""

    path = "/api/jobs"
    dependencies = {"db": Provide(db_dependency)}

    @get("/")
    async def list_jobs(
        self,
        db: Database,
        status: Annotated[JobStatus | None, Parameter(query="status")] = None,
        source: Annotated[str | None, Parameter(query="source")] = None,
        company: Annotated[str | None, Parameter(query="company")] = None,
        min_score: Annotated[float | None, Parameter(query="min_score", ge=0, le=100)] = None,
        work_type: Annotated[WorkType | None, Parameter(query="work_type")] = None,
        page: Annotated[int, Parameter(query="page", ge=1)] = 1,
        page_size: Annotated[int, Parameter(query="page_size", ge=1, le=100)] = 20,
    ) -> JobList:
        """List jobs with optional filters."""
        # Build WHERE clause
        conditions = []
        params: list = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if company:
            conditions.append("company LIKE ?")
            params.append(f"%{company}%")
        if min_score is not None:
            conditions.append("fit_score >= ?")
            params.append(min_score)
        if work_type:
            conditions.append("work_type = ?")
            params.append(work_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM jobs WHERE {where_clause}"
        count_row = await db.fetchone(count_sql, tuple(params))
        total = count_row[0] if count_row else 0

        # Get paginated results
        offset = (page - 1) * page_size
        query_sql = f"""
            SELECT * FROM jobs
            WHERE {where_clause}
            ORDER BY scraped_at DESC
            LIMIT ? OFFSET ?
        """
        rows = await db.fetchall(query_sql, tuple(params + [page_size, offset]))

        items = [Job(**dict(row)) for row in rows]
        return JobList(items=items, total=total, page=page, page_size=page_size)

    @get("/{job_id:str}")
    async def get_job(self, db: Database, job_id: str) -> Job:
        """Get a single job by ID."""
        row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not row:
            from litestar.exceptions import NotFoundException

            raise NotFoundException(f"Job not found: {job_id}")
        return Job(**dict(row))

    @post("/")
    async def create_job(self, db: Database, data: JobCreate) -> Job:
        """Create a new job."""
        # Generate ID if not provided
        job_id = data.id or generate_job_id(data.url)

        await db.execute(
            """
            INSERT INTO jobs (id, url, source, title, company, location, work_type,
                            salary_min, salary_max, description, requirements, posted_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                data.url,
                data.source,
                data.title,
                data.company,
                data.location,
                data.work_type,
                data.salary_min,
                data.salary_max,
                data.description,
                data.requirements,
                data.posted_date,
            ),
        )
        await db.commit()

        row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return Job(**dict(row))

    @patch("/{job_id:str}")
    async def update_job(
        self, db: Database, job_id: str, data: JobUpdate
    ) -> Job:
        """Update a job's status, notes, or fit score."""
        # Build SET clause from non-None fields
        updates = []
        params = []

        if data.status is not None:
            updates.append("status = ?")
            params.append(data.status)
        if data.notes is not None:
            updates.append("notes = ?")
            params.append(data.notes)
        if data.fit_score is not None:
            updates.append("fit_score = ?")
            params.append(data.fit_score)
        if data.fit_rationale is not None:
            updates.append("fit_rationale = ?")
            params.append(data.fit_rationale)

        if not updates:
            # No updates, just return the current job
            return await self.get_job(db, job_id)

        params.append(job_id)
        await db.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        await db.commit()

        return await self.get_job(db, job_id)

    @delete("/{job_id:str}", status_code=200)
    async def delete_job(self, db: Database, job_id: str) -> MessageResponse:
        """Delete a job."""
        await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await db.commit()
        return MessageResponse(message=f"Job {job_id} deleted")

    @get("/search")
    async def search_jobs(
        self,
        db: Database,
        q: Annotated[str, Parameter(query="q", min_length=1)],
        page: Annotated[int, Parameter(query="page", ge=1)] = 1,
        page_size: Annotated[int, Parameter(query="page_size", ge=1, le=100)] = 20,
    ) -> JobList:
        """Full-text search jobs using FTS5."""
        offset = (page - 1) * page_size

        # Get total count
        count_sql = """
            SELECT COUNT(*) FROM jobs_fts WHERE jobs_fts MATCH ?
        """
        count_row = await db.fetchone(count_sql, (q,))
        total = count_row[0] if count_row else 0

        # Get matching jobs
        query_sql = """
            SELECT jobs.* FROM jobs
            JOIN jobs_fts ON jobs.rowid = jobs_fts.rowid
            WHERE jobs_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
        """
        rows = await db.fetchall(query_sql, (q, page_size, offset))

        items = [Job(**dict(row)) for row in rows]
        return JobList(items=items, total=total, page=page, page_size=page_size)
