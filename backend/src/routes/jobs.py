"""Job routes for CRUD operations and search."""

import hashlib
import json
import logging
from typing import Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from litestar.params import Parameter

from ..db import Database, db_dependency
from ..models import (
    EmbedBatchResponse,
    EmbedJobResponse,
    Job,
    JobCreate,
    JobList,
    JobStatus,
    JobUpdate,
    MessageResponse,
    ScoreBatchRequest,
    ScoreBatchResponse,
    ScoreJobResponse,
    WorkType,
)
from ..services.embeddings import EmbeddingService, cosine_similarity
from ..services.scorer import ScorerService

logger = logging.getLogger(__name__)


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
            row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if not row:
                raise NotFoundException(f"Job not found: {job_id}")
            return Job(**dict(row))

        params.append(job_id)
        await db.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        await db.commit()

        row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not row:
            raise NotFoundException(f"Job not found: {job_id}")
        return Job(**dict(row))

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

    # --- Scoring Endpoints ---

    @post("/{job_id:str}/score")
    async def score_job(self, db: Database, job_id: str) -> ScoreJobResponse:
        """Score a single job against the user's profile."""
        row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not row:
            raise NotFoundException(f"Job not found: {job_id}")

        job = dict(row)
        scorer = ScorerService()

        try:
            result = await scorer.score_job(job)
        finally:
            await scorer.close()

        # Update job with score
        await db.execute(
            "UPDATE jobs SET fit_score = ?, fit_rationale = ? WHERE id = ?",
            (result["score"], result["rationale"], job_id),
        )
        await db.commit()

        return ScoreJobResponse(
            job_id=job_id,
            score=result["score"],
            rationale=result["rationale"],
            matching_skills=result["matching_skills"],
            missing_skills=result["missing_skills"],
            dealbreaker_triggered=result["dealbreaker_triggered"],
        )

    @post("/score-batch")
    async def score_batch(
        self, db: Database, data: ScoreBatchRequest
    ) -> ScoreBatchResponse:
        """Score multiple jobs against the user's profile."""
        results = []
        scorer = ScorerService()

        try:
            profile = scorer.load_profile()

            for job_id in data.job_ids:
                row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
                if not row:
                    logger.warning(f"Job not found for scoring: {job_id}")
                    continue

                job = dict(row)
                result = await scorer.score_job(job, profile)

                # Update job with score
                await db.execute(
                    "UPDATE jobs SET fit_score = ?, fit_rationale = ? WHERE id = ?",
                    (result["score"], result["rationale"], job_id),
                )

                results.append(
                    ScoreJobResponse(
                        job_id=job_id,
                        score=result["score"],
                        rationale=result["rationale"],
                        matching_skills=result["matching_skills"],
                        missing_skills=result["missing_skills"],
                        dealbreaker_triggered=result["dealbreaker_triggered"],
                    )
                )
        finally:
            await scorer.close()

        await db.commit()
        return ScoreBatchResponse(scored=len(results), results=results)

    # --- Embedding Endpoints ---

    @post("/{job_id:str}/embed")
    async def embed_job(self, db: Database, job_id: str) -> EmbedJobResponse:
        """Generate embedding for a single job."""
        row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not row:
            raise NotFoundException(f"Job not found: {job_id}")

        job = dict(row)
        service = EmbeddingService()

        # Generate embedding
        text = service.job_to_text(job)
        embedding = service.generate_embedding(text)

        # Store as JSON blob
        embedding_blob = json.dumps(embedding).encode("utf-8")
        await db.execute(
            "UPDATE jobs SET embedding = ? WHERE id = ?",
            (embedding_blob, job_id),
        )
        await db.commit()

        return EmbedJobResponse(job_id=job_id, embedded=True)

    @post("/embed-all")
    async def embed_all_jobs(self, db: Database) -> EmbedBatchResponse:
        """Generate embeddings for all jobs without embeddings."""
        # Get jobs without embeddings
        rows = await db.fetchall(
            "SELECT id, title, company, description, requirements FROM jobs WHERE embedding IS NULL"
        )

        if not rows:
            return EmbedBatchResponse(total=0, embedded=0, skipped=0)

        service = EmbeddingService()
        embedded = 0
        skipped = 0

        for row in rows:
            job = dict(row)
            try:
                text = service.job_to_text(job)
                if not text.strip():
                    skipped += 1
                    continue

                embedding = service.generate_embedding(text)
                embedding_blob = json.dumps(embedding).encode("utf-8")

                await db.execute(
                    "UPDATE jobs SET embedding = ? WHERE id = ?",
                    (embedding_blob, job["id"]),
                )
                embedded += 1
            except Exception as e:
                logger.error(f"Failed to embed job {job['id']}: {e}")
                skipped += 1

        await db.commit()
        return EmbedBatchResponse(total=len(rows), embedded=embedded, skipped=skipped)

    @get("/similar/{job_id:str}")
    async def find_similar(
        self,
        db: Database,
        job_id: str,
        limit: Annotated[int, Parameter(query="limit", ge=1, le=50)] = 10,
    ) -> JobList:
        """Find jobs similar to a given job using vector similarity."""
        # Get the source job's embedding
        row = await db.fetchone(
            "SELECT embedding FROM jobs WHERE id = ?", (job_id,)
        )
        if not row:
            raise NotFoundException(f"Job not found: {job_id}")

        if not row["embedding"]:
            raise NotFoundException(
                f"Job {job_id} has no embedding. Run POST /api/jobs/{job_id}/embed first."
            )

        source_embedding = json.loads(row["embedding"])

        # Get all other jobs with embeddings
        rows = await db.fetchall(
            "SELECT * FROM jobs WHERE id != ? AND embedding IS NOT NULL",
            (job_id,),
        )

        # Calculate similarities
        similarities = []
        for r in rows:
            job_dict = dict(r)
            embedding = json.loads(job_dict["embedding"])
            similarity = cosine_similarity(source_embedding, embedding)
            similarities.append((similarity, job_dict))

        # Sort by similarity (highest first) and take top N
        similarities.sort(key=lambda x: x[0], reverse=True)
        top_jobs = [job for _, job in similarities[:limit]]

        # Remove embedding from response (too large)
        items = []
        for job in top_jobs:
            job.pop("embedding", None)
            items.append(Job(**job))

        return JobList(items=items, total=len(items), page=1, page_size=limit)

    @get("/semantic-search")
    async def semantic_search(
        self,
        db: Database,
        q: Annotated[str, Parameter(query="q", min_length=1)],
        limit: Annotated[int, Parameter(query="limit", ge=1, le=100)] = 20,
    ) -> JobList:
        """Search jobs using semantic similarity to a query string."""
        service = EmbeddingService()

        # Generate query embedding
        query_embedding = service.generate_embedding(q)

        # Get all jobs with embeddings
        rows = await db.fetchall(
            "SELECT * FROM jobs WHERE embedding IS NOT NULL"
        )

        if not rows:
            return JobList(items=[], total=0, page=1, page_size=limit)

        # Calculate similarities
        similarities = []
        for r in rows:
            job_dict = dict(r)
            embedding = json.loads(job_dict["embedding"])
            similarity = cosine_similarity(query_embedding, embedding)
            similarities.append((similarity, job_dict))

        # Sort by similarity (highest first) and take top N
        similarities.sort(key=lambda x: x[0], reverse=True)
        top_jobs = [job for _, job in similarities[:limit]]

        # Remove embedding from response
        items = []
        for job in top_jobs:
            job.pop("embedding", None)
            items.append(Job(**job))

        return JobList(items=items, total=len(items), page=1, page_size=limit)
