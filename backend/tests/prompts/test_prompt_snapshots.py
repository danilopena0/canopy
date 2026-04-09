"""Snapshot / golden file tests for prompt templates.

System prompts are snapshotted as-is (static strings). User prompt templates
are rendered with a fixed canonical input and snapshotted.

On first run the snapshot files are written to tests/prompts/snapshots/ and
the test passes. On subsequent runs any deviation causes a failure.

To accept intentional changes:
    pytest tests/prompts/test_prompt_snapshots.py --update-snapshots
"""

import pytest

from src.services.scorer import SCORING_SYSTEM_PROMPT, SCORING_USER_PROMPT
from src.services.cover import COVER_SYSTEM_PROMPT, COVER_USER_PROMPT
from src.services.resume import TAILOR_SYSTEM_PROMPT, TAILOR_USER_PROMPT
from src.services.project_matcher import SYSTEM_PROMPT as PM_SYSTEM_PROMPT
from src.services.project_matcher import USER_PROMPT as PM_USER_PROMPT
from .conftest import MockLLMProvider

# ---------------------------------------------------------------------------
# Canonical render inputs — keep these stable; changing them invalidates snapshots
# ---------------------------------------------------------------------------

CANONICAL_PROFILE = {
    "name": "Alex Rivera",
    "target_titles": ["Data Scientist", "ML Engineer"],
    "experience_years": 6,
    "skills": {
        "languages": ["Python", "SQL"],
        "ml_tools": ["XGBoost", "PyTorch"],
        "platforms": ["AWS"],
        "other": ["NLP", "MLOps"],
    },
    "locations": ["San Antonio, TX", "Remote"],
    "work_types": ["hybrid", "remote"],
    "industries": ["Finance", "Tech"],
    "min_salary": 120000,
    "dealbreakers": ["clearance required"],
}

CANONICAL_JOB = {
    "title": "Senior Data Scientist",
    "company": "USAA",
    "location": "San Antonio, TX",
    "work_type": "hybrid",
    "salary_min": 130000,
    "salary_max": 160000,
    "description": "Build ML models to detect fraud and improve member experience.",
    "requirements": "5+ years experience. Python, SQL, scikit-learn. AWS preferred.",
}

CANONICAL_PROJECTS = "## Banyan\nFraud detection. XGBoost, AWS SageMaker.\n\n## Maple\nNLP classifier. PyTorch."


# ---------------------------------------------------------------------------
# System prompt snapshots (static — no rendering)
# ---------------------------------------------------------------------------

def test_snapshot_scorer_system_prompt(snapshot):
    snapshot(SCORING_SYSTEM_PROMPT, "scorer_system_prompt")


def test_snapshot_cover_system_prompt(snapshot):
    snapshot(COVER_SYSTEM_PROMPT, "cover_system_prompt")


def test_snapshot_tailor_system_prompt(snapshot):
    snapshot(TAILOR_SYSTEM_PROMPT, "tailor_system_prompt")


def test_snapshot_project_matcher_system_prompt(snapshot):
    snapshot(PM_SYSTEM_PROMPT, "project_matcher_system_prompt")


# ---------------------------------------------------------------------------
# Rendered user prompt snapshots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snapshot_scorer_rendered_prompt(snapshot, sample_job, sample_profile):
    """Snapshot the fully-rendered scorer prompt with canonical inputs."""
    from src.services.scorer import ScorerService

    llm = MockLLMProvider(json_response={
        "score": 80, "rationale": "good", "matching_skills": [], "missing_skills": [],
        "dealbreaker_triggered": None,
    })
    service = ScorerService(llm=llm)
    await service.score_job(CANONICAL_JOB, CANONICAL_PROFILE)

    snapshot(llm.last_prompt, "scorer_rendered_prompt")


@pytest.mark.asyncio
async def test_snapshot_cover_rendered_prompt(snapshot):
    """Snapshot the fully-rendered cover letter prompt with canonical inputs."""
    from src.services.cover import CoverLetterService

    llm = MockLLMProvider(json_response={"cover_letter": "...", "tone_used": "professional"})
    service = CoverLetterService(llm=llm)
    service.get_resume_summary = lambda: "Alex Rivera — Data scientist with 6 years experience."
    service.load_template = lambda name=None: None

    await service.generate_cover_letter(
        job_title=CANONICAL_JOB["title"],
        company=CANONICAL_JOB["company"],
        location=CANONICAL_JOB["location"],
        work_type=CANONICAL_JOB["work_type"],
        job_description=CANONICAL_JOB["description"],
        requirements=CANONICAL_JOB["requirements"],
        profile=CANONICAL_PROFILE,
    )

    snapshot(llm.last_prompt, "cover_rendered_prompt")


@pytest.mark.asyncio
async def test_snapshot_tailor_rendered_prompt(snapshot):
    """Snapshot the fully-rendered resume tailor prompt with canonical inputs."""
    from src.services.resume import ResumeService

    llm = MockLLMProvider(json_response={"tailored_resume": "# Resume", "highlights": []})
    service = ResumeService(llm=llm)
    service.load_master_resume = lambda: "# Alex Rivera\n\nData scientist. Python, XGBoost, AWS."
    service.load_experience_documents = lambda: {}

    await service.tailor_resume(
        job_title=CANONICAL_JOB["title"],
        company=CANONICAL_JOB["company"],
        job_description=CANONICAL_JOB["description"],
        requirements=CANONICAL_JOB["requirements"],
        profile=CANONICAL_PROFILE,
    )

    snapshot(llm.last_prompt, "tailor_rendered_prompt")


@pytest.mark.asyncio
async def test_snapshot_project_matcher_rendered_prompt(snapshot):
    """Snapshot the fully-rendered project matcher prompt with canonical inputs."""
    from src.services.project_matcher import ProjectMatcherService

    llm = MockLLMProvider(json_response={
        "lead_project": "Banyan", "projects": [], "skill_gaps": [],
    })
    service = ProjectMatcherService(llm=llm)
    service._load_projects_catalogue = lambda: CANONICAL_PROJECTS

    await service.match_projects(
        job_title=CANONICAL_JOB["title"],
        company=CANONICAL_JOB["company"],
        job_description=CANONICAL_JOB["description"],
        requirements=CANONICAL_JOB["requirements"],
    )

    snapshot(llm.last_prompt, "project_matcher_rendered_prompt")
