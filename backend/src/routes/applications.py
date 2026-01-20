"""Application routes for tracking job applications."""

from typing import Annotated

from litestar import Controller, get, patch, post
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from litestar.params import Parameter

from ..db import Database, db_dependency
from ..models import (
    Application,
    ApplicationCreate,
    ApplicationUpdate,
    MessageResponse,
)


class ApplicationController(Controller):
    """Controller for application-related endpoints."""

    path = "/api/applications"
    dependencies = {"db": Provide(db_dependency)}

    @get("/")
    async def list_applications(
        self,
        db: Database,
        job_id: Annotated[str | None, Parameter(query="job_id")] = None,
    ) -> list[Application]:
        """List all applications, optionally filtered by job."""
        if job_id:
            rows = await db.fetchall(
                "SELECT * FROM applications WHERE job_id = ? ORDER BY tailored_at DESC",
                (job_id,),
            )
        else:
            rows = await db.fetchall(
                "SELECT * FROM applications ORDER BY tailored_at DESC"
            )
        return [Application(**dict(row)) for row in rows]

    @get("/{application_id:int}")
    async def get_application(
        self, db: Database, application_id: int
    ) -> Application:
        """Get a single application by ID."""
        row = await db.fetchone(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        )
        if not row:
            raise NotFoundException(f"Application not found: {application_id}")
        return Application(**dict(row))

    @post("/{job_id:str}/tailor")
    async def tailor_resume(
        self, db: Database, job_id: str
    ) -> MessageResponse:
        """Generate a tailored resume for a job.

        TODO: Implement in Phase 4 with resume tailoring logic.
        """
        # Verify job exists
        job = await db.fetchone("SELECT id FROM jobs WHERE id = ?", (job_id,))
        if not job:
            raise NotFoundException(f"Job not found: {job_id}")

        return MessageResponse(
            message="Resume tailoring will be implemented in Phase 4"
        )

    @post("/{job_id:str}/cover")
    async def generate_cover_letter(
        self, db: Database, job_id: str
    ) -> MessageResponse:
        """Generate a cover letter for a job.

        TODO: Implement in Phase 4 with cover letter generation logic.
        """
        # Verify job exists
        job = await db.fetchone("SELECT id FROM jobs WHERE id = ?", (job_id,))
        if not job:
            raise NotFoundException(f"Job not found: {job_id}")

        return MessageResponse(
            message="Cover letter generation will be implemented in Phase 4"
        )

    @post("/")
    async def create_application(
        self, db: Database, data: ApplicationCreate
    ) -> Application:
        """Create a new application record."""
        # Verify job exists
        job = await db.fetchone(
            "SELECT id FROM jobs WHERE id = ?", (data.job_id,)
        )
        if not job:
            raise NotFoundException(f"Job not found: {data.job_id}")

        cursor = await db.execute(
            """
            INSERT INTO applications (job_id, resume_version, cover_letter)
            VALUES (?, ?, ?)
            """,
            (data.job_id, data.resume_version, data.cover_letter),
        )
        await db.commit()

        return await self.get_application(db, cursor.lastrowid)

    @patch("/{application_id:int}")
    async def update_application(
        self, db: Database, application_id: int, data: ApplicationUpdate
    ) -> Application:
        """Update an application."""
        # Build SET clause from non-None fields
        updates = []
        params = []

        if data.resume_version is not None:
            updates.append("resume_version = ?")
            params.append(data.resume_version)
        if data.cover_letter is not None:
            updates.append("cover_letter = ?")
            params.append(data.cover_letter)
        if data.applied_at is not None:
            updates.append("applied_at = ?")
            params.append(data.applied_at.isoformat())
        if data.response is not None:
            updates.append("response = ?")
            params.append(data.response)

        if not updates:
            return await self.get_application(db, application_id)

        params.append(application_id)
        await db.execute(
            f"UPDATE applications SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        await db.commit()

        return await self.get_application(db, application_id)
