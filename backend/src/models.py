"""Pydantic models for request/response validation."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


# Job status enum
JobStatus = Literal["new", "reviewed", "applied", "rejected", "archived"]

# Work type enum
WorkType = Literal["remote", "hybrid", "onsite"]

# Cover letter tone enum
CoverLetterTone = Literal["professional", "enthusiastic", "casual"]


# --- Job Models ---


class JobBase(BaseModel):
    """Base job model with common fields."""

    url: str
    source: str
    title: str
    company: str
    location: str | None = None
    work_type: WorkType | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    description: str | None = None
    requirements: str | None = None  # JSON array as string
    posted_date: date | None = None


class JobCreate(JobBase):
    """Model for creating a new job."""

    id: str  # Hash of URL


class JobUpdate(BaseModel):
    """Model for updating a job."""

    status: JobStatus | None = None
    notes: str | None = None
    fit_score: float | None = Field(None, ge=0, le=100)
    fit_rationale: str | None = None


class Job(JobBase):
    """Complete job model with all fields."""

    id: str
    scraped_at: datetime
    fit_score: float | None = None
    fit_rationale: str | None = None
    status: JobStatus = "new"
    notes: str | None = None
    dedup_key: str | None = None
    duplicate_of: str | None = None

    class Config:
        from_attributes = True


class JobList(BaseModel):
    """Paginated list of jobs."""

    items: list[Job]
    total: int
    page: int
    page_size: int


# --- Search Run Models ---


class SearchRunCreate(BaseModel):
    """Model for recording a search run."""

    sources: list[str]
    jobs_found: int
    new_jobs: int
    duration_seconds: float


class SearchRun(BaseModel):
    """Complete search run model."""

    id: int
    run_at: datetime
    sources: str  # JSON array as string
    jobs_found: int
    new_jobs: int
    duration_seconds: float

    class Config:
        from_attributes = True


# --- Application Models ---


class ApplicationCreate(BaseModel):
    """Model for creating an application."""

    job_id: str
    resume_version: str | None = None
    cover_letter: str | None = None
    tailored_resume: str | None = None
    resume_highlights: str | None = None  # JSON array as string
    cover_tone: CoverLetterTone | None = None


class ApplicationUpdate(BaseModel):
    """Model for updating an application."""

    resume_version: str | None = None
    cover_letter: str | None = None
    tailored_resume: str | None = None
    resume_highlights: str | None = None
    cover_tone: CoverLetterTone | None = None
    applied_at: datetime | None = None
    response: str | None = None


class Application(BaseModel):
    """Complete application model."""

    id: int
    job_id: str
    resume_version: str | None = None
    cover_letter: str | None = None
    tailored_resume: str | None = None
    resume_highlights: str | None = None  # JSON array as string
    cover_tone: CoverLetterTone | None = None
    tailored_at: datetime
    applied_at: datetime | None = None
    response: str | None = None

    class Config:
        from_attributes = True


class TailorResumeRequest(BaseModel):
    """Request model for tailoring a resume."""

    pass  # No additional options needed for now


class TailorResumeResponse(BaseModel):
    """Response model for tailored resume."""

    application_id: int
    job_id: str
    tailored_resume: str
    highlights: list[str]


class GenerateCoverRequest(BaseModel):
    """Request model for generating a cover letter."""

    tone: CoverLetterTone = "professional"
    template_name: str | None = None


class GenerateCoverResponse(BaseModel):
    """Response model for generated cover letter."""

    application_id: int
    job_id: str
    cover_letter: str
    tone_used: str


class DocumentInfo(BaseModel):
    """Document metadata."""

    filename: str
    path: str
    size_bytes: int
    doc_type: Literal["resume", "experience", "template"]


class DocumentList(BaseModel):
    """List of available documents."""

    documents: list[DocumentInfo]
    has_resume: bool


# --- Company Source Models ---


class CompanySourceCreate(BaseModel):
    """Model for creating a company source."""

    company_name: str
    careers_url: str
    scrape_config: str | None = None  # JSON config
    category: str | None = None


class CompanySourceUpdate(BaseModel):
    """Model for updating a company source."""

    company_name: str | None = None
    careers_url: str | None = None
    scrape_config: str | None = None
    category: str | None = None
    enabled: bool | None = None


class CompanySource(BaseModel):
    """Complete company source model."""

    id: int
    company_name: str
    careers_url: str
    scrape_config: str | None = None
    category: str | None = None
    enabled: bool = True

    class Config:
        from_attributes = True


# --- Query Parameters ---


class JobFilterParams(BaseModel):
    """Query parameters for filtering jobs."""

    status: JobStatus | None = None
    source: str | None = None
    company: str | None = None
    min_score: float | None = Field(None, ge=0, le=100)
    work_type: WorkType | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class SearchParams(BaseModel):
    """Query parameters for full-text search."""

    q: str = Field(..., min_length=1)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# --- Response Models ---


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    database: str = "connected"


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
