"""Prompt length / token budget tests.

Worst-case inputs are constructed and the rendered prompt character count is
asserted to stay within a practical ceiling. The ceiling is not the hard model
context limit — it is a quality threshold above which long-range reasoning
degrades and costs spike.

Approximation: 1 token ≈ 4 characters (English prose).

Limits per service (chars / approx tokens):
  Scorer         : 20 000 /  5 000  — profile is compact; job text dominates
  Cover letter   : 15 000 /  3 750  — resume already truncated to 1 000 chars
  Resume tailor  : 80 000 / 20 000  — full resume + experience docs allowed
  Project matcher: 40 000 / 10 000  — catalogue can be large
"""

import pytest

from src.services.scorer import ScorerService, SCORING_USER_PROMPT, SCORING_SYSTEM_PROMPT
from src.services.cover import CoverLetterService
from src.services.resume import ResumeService
from src.services.project_matcher import ProjectMatcherService
from .conftest import MockLLMProvider

# Characters per service — change these when you deliberately increase prompt scope
SCORER_CHAR_LIMIT = 20_000
COVER_CHAR_LIMIT = 15_000
TAILOR_CHAR_LIMIT = 80_000
MATCHER_CHAR_LIMIT = 40_000

LOREM = (
    "Machine learning models require careful feature engineering and rigorous "
    "validation against held-out data sets to avoid overfitting. Python and SQL "
    "are essential tools for any modern data scientist working in financial services. "
)


def long_text(target_chars: int) -> str:
    """Return a string of approximately target_chars characters."""
    reps = (target_chars // len(LOREM)) + 1
    return (LOREM * reps)[:target_chars]


GOOD_SCORE_RESPONSE = {
    "score": 70, "rationale": "ok", "matching_skills": [], "missing_skills": [],
    "dealbreaker_triggered": None,
}
GOOD_COVER_RESPONSE = {"cover_letter": "Dear Hiring Manager...", "tone_used": "professional"}
GOOD_TAILOR_RESPONSE = {"tailored_resume": "# Resume", "highlights": ["highlight"]}
GOOD_MATCH_RESPONSE = {
    "lead_project": "Banyan",
    "projects": [{"name": "Banyan", "relevance": "x", "star_story": "x",
                  "addresses_requirements": [], "technical_angle": "x"}],
    "skill_gaps": [],
}


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scorer_prompt_within_limit_with_long_job(sample_profile):
    job = {
        "title": "Data Scientist",
        "company": "USAA",
        "location": "San Antonio, TX",
        "work_type": "hybrid",
        "salary_min": 130000,
        "salary_max": 160000,
        "description": long_text(8000),
        "requirements": long_text(4000),
    }
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(job, sample_profile)

    assert len(llm.last_prompt) <= SCORER_CHAR_LIMIT, (
        f"Scorer prompt is {len(llm.last_prompt):,} chars — exceeds {SCORER_CHAR_LIMIT:,} limit. "
        "Consider truncating description/requirements before sending."
    )


@pytest.mark.asyncio
async def test_scorer_system_prompt_is_concise():
    """System prompt should be a tight persona — not a wall of instructions."""
    assert len(SCORING_SYSTEM_PROMPT) <= 500, (
        f"Scoring system prompt is {len(SCORING_SYSTEM_PROMPT)} chars. "
        "Keep system prompts under 500 chars to leave room for content."
    )


# ---------------------------------------------------------------------------
# Cover letter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cover_prompt_within_limit_with_long_job(sample_profile):
    long_description = long_text(6000)
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = CoverLetterService(llm=llm)
    service.get_resume_summary = lambda: long_text(1000)  # already truncated by service
    service.load_template = lambda name=None: None

    await service.generate_cover_letter(
        job_title="Senior Data Scientist",
        company="USAA",
        location="San Antonio, TX",
        work_type="hybrid",
        job_description=long_description,
        requirements=long_text(2000),
        profile=sample_profile,
    )

    assert len(llm.last_prompt) <= COVER_CHAR_LIMIT, (
        f"Cover prompt is {len(llm.last_prompt):,} chars — exceeds {COVER_CHAR_LIMIT:,} limit."
    )


@pytest.mark.asyncio
async def test_cover_resume_summary_is_truncated(sample_profile):
    """CoverLetterService already truncates to 1 000 chars — verify the real method."""
    import tempfile, os
    from pathlib import Path

    long_resume = "A" * 5000
    service = CoverLetterService(llm=MockLLMProvider())
    with tempfile.TemporaryDirectory() as tmpdir:
        resume_path = Path(tmpdir) / "resume.md"
        resume_path.write_text(long_resume)
        service._profile_path = Path(tmpdir)
        summary = service.get_resume_summary()

    assert len(summary) <= 1010  # 1000 chars + "..."


# ---------------------------------------------------------------------------
# Resume tailor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tailor_prompt_within_limit_with_long_inputs(sample_profile):
    long_resume = long_text(10_000)
    long_exp_doc = long_text(5_000)
    long_description = long_text(5_000)

    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = ResumeService(llm=llm)
    service.load_master_resume = lambda: long_resume
    service.load_experience_documents = lambda: {"leadership": long_exp_doc}

    await service.tailor_resume(
        job_title="Senior Data Scientist",
        company="USAA",
        job_description=long_description,
        requirements=long_text(2_000),
        profile=sample_profile,
    )

    assert len(llm.last_prompt) <= TAILOR_CHAR_LIMIT, (
        f"Tailor prompt is {len(llm.last_prompt):,} chars — exceeds {TAILOR_CHAR_LIMIT:,} limit. "
        "Consider truncating experience docs or splitting into two calls."
    )


# ---------------------------------------------------------------------------
# Project matcher
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matcher_prompt_within_limit_with_large_catalogue(sample_job):
    large_catalogue = long_text(20_000)

    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = ProjectMatcherService(llm=llm)
    service._load_projects_catalogue = lambda: large_catalogue

    await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=long_text(5_000),
        requirements=long_text(2_000),
    )

    assert len(llm.last_prompt) <= MATCHER_CHAR_LIMIT, (
        f"Matcher prompt is {len(llm.last_prompt):,} chars — exceeds {MATCHER_CHAR_LIMIT:,} limit. "
        "Consider summarising or chunking the projects catalogue."
    )
