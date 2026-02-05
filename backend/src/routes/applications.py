"""Application routes for tracking job applications."""

import json
import logging
from pathlib import Path
from typing import Annotated, Any

from litestar import Controller, get, patch, post
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from litestar.params import Parameter

from ..config import get_settings
from ..db import Database, db_dependency
from ..models import (
    Application,
    ApplicationCreate,
    ApplicationUpdate,
    DocumentInfo,
    DocumentList,
    GenerateCoverRequest,
    GenerateCoverResponse,
    TailorResumeRequest,
    TailorResumeResponse,
)
from ..services.cover import CoverLetterService
from ..services.resume import ResumeService

logger = logging.getLogger(__name__)


def _load_profile() -> dict[str, Any]:
    """Load user profile from file."""
    settings = get_settings()
    db_path = Path(settings.database_path)
    profile_path = db_path.parent / "profile.json"

    if profile_path.exists():
        with open(profile_path) as f:
            return json.load(f)

    # Return default profile
    return {
        "name": "",
        "target_titles": ["Data Scientist", "ML Engineer", "AI Engineer"],
        "skills": {"languages": [], "ml_tools": [], "platforms": [], "other": []},
        "experience_years": 0,
        "locations": ["San Antonio, TX", "Austin, TX", "Remote"],
        "work_types": ["remote", "hybrid"],
        "industries": [],
        "min_salary": None,
        "dealbreakers": [],
    }


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
        self, db: Database, job_id: str, data: TailorResumeRequest | None = None
    ) -> TailorResumeResponse:
        """Generate a tailored resume for a job.

        Uses the master resume and experience documents from backend/profile/
        along with the job description to generate a tailored resume via LLM.
        """
        # Get job details
        job_row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not job_row:
            raise NotFoundException(f"Job not found: {job_id}")

        job = dict(job_row)

        # Load user profile
        profile = _load_profile()

        # Generate tailored resume
        resume_service = ResumeService()
        try:
            result = await resume_service.tailor_resume(
                job_title=job["title"],
                company=job["company"],
                job_description=job.get("description") or "",
                requirements=job.get("requirements"),
                profile=profile,
            )
        finally:
            await resume_service.close()

        # Check for existing application or create new one
        existing = await db.fetchone(
            "SELECT id FROM applications WHERE job_id = ?", (job_id,)
        )

        highlights_json = json.dumps(result["highlights"])

        if existing:
            app_id = existing["id"]
            await db.execute(
                """
                UPDATE applications
                SET tailored_resume = ?, resume_highlights = ?, tailored_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (result["tailored_resume"], highlights_json, app_id),
            )
        else:
            cursor = await db.execute(
                """
                INSERT INTO applications (job_id, tailored_resume, resume_highlights)
                VALUES (?, ?, ?)
                """,
                (job_id, result["tailored_resume"], highlights_json),
            )
            app_id = cursor.lastrowid

        await db.commit()
        logger.info(f"Tailored resume generated for job {job_id}")

        return TailorResumeResponse(
            application_id=app_id,
            job_id=job_id,
            tailored_resume=result["tailored_resume"],
            highlights=result["highlights"],
        )

    @post("/{job_id:str}/cover")
    async def generate_cover_letter(
        self, db: Database, job_id: str, data: GenerateCoverRequest | None = None
    ) -> GenerateCoverResponse:
        """Generate a cover letter for a job.

        Uses the user profile and resume to generate a personalized cover letter
        via LLM with the specified tone.
        """
        # Default request if none provided
        if data is None:
            data = GenerateCoverRequest()

        # Get job details
        job_row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not job_row:
            raise NotFoundException(f"Job not found: {job_id}")

        job = dict(job_row)

        # Load user profile
        profile = _load_profile()

        # Generate cover letter
        cover_service = CoverLetterService()
        try:
            result = await cover_service.generate_cover_letter(
                job_title=job["title"],
                company=job["company"],
                location=job.get("location"),
                work_type=job.get("work_type"),
                job_description=job.get("description") or "",
                requirements=job.get("requirements"),
                profile=profile,
                template_name=data.template_name,
            )
        finally:
            await cover_service.close()

        # Check for existing application or create new one
        existing = await db.fetchone(
            "SELECT id FROM applications WHERE job_id = ?", (job_id,)
        )

        if existing:
            app_id = existing["id"]
            await db.execute(
                """
                UPDATE applications
                SET cover_letter = ?, cover_tone = ?, tailored_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (result["cover_letter"], result["tone_used"], app_id),
            )
        else:
            cursor = await db.execute(
                """
                INSERT INTO applications (job_id, cover_letter, cover_tone)
                VALUES (?, ?, ?)
                """,
                (job_id, result["cover_letter"], result["tone_used"]),
            )
            app_id = cursor.lastrowid

        await db.commit()
        logger.info(f"Cover letter generated for job {job_id}")

        return GenerateCoverResponse(
            application_id=app_id,
            job_id=job_id,
            cover_letter=result["cover_letter"],
            tone_used=result["tone_used"],
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
            INSERT INTO applications (
                job_id, resume_version, cover_letter,
                tailored_resume, resume_highlights, cover_tone
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data.job_id,
                data.resume_version,
                data.cover_letter,
                data.tailored_resume,
                data.resume_highlights,
                data.cover_tone,
            ),
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
        if data.tailored_resume is not None:
            updates.append("tailored_resume = ?")
            params.append(data.tailored_resume)
        if data.resume_highlights is not None:
            updates.append("resume_highlights = ?")
            params.append(data.resume_highlights)
        if data.cover_tone is not None:
            updates.append("cover_tone = ?")
            params.append(data.cover_tone)
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


class DocumentController(Controller):
    """Controller for document management endpoints."""

    path = "/api/documents"

    @get("/")
    async def list_documents(self) -> DocumentList:
        """List all available profile documents.

        Returns metadata about documents in backend/profile/ directory.
        """
        resume_service = ResumeService()
        docs = resume_service.list_documents()
        has_resume = resume_service.has_resume()

        return DocumentList(
            documents=[DocumentInfo(**doc) for doc in docs],
            has_resume=has_resume,
        )
