"""Prompt engineering tests for the resume tailoring service.

These tests verify:
1. Master resume content reaches the prompt
2. Job title and company are present
3. Output keys are correct (tailored_resume, highlights)
4. Highlights is always a list
5. FileNotFoundError surfaces when no resume exists
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.services.resume import ResumeService, TAILOR_SYSTEM_PROMPT
from .conftest import MockLLMProvider


GOOD_TAILOR_RESPONSE = {
    "tailored_resume": "# Alex Rivera\n\nTailored for Senior Data Scientist at USAA...",
    "highlights": [
        "Fraud detection with XGBoost — directly relevant to USAA's financial ML needs",
        "6 years of experience meets the 5+ requirement",
        "AWS SageMaker aligns with cloud platform expectations",
    ],
}


def make_service(
    llm: MockLLMProvider,
    resume_content: str = "Master resume content.",
    experience_docs: dict | None = None,
) -> ResumeService:
    """Create a ResumeService with mocked file I/O."""
    service = ResumeService(llm=llm)
    service.load_master_resume = lambda: resume_content
    service.load_experience_documents = lambda: experience_docs or {}
    return service


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prompt_contains_master_resume(sample_job, sample_profile):
    resume = "UNIQUE RESUME MARKER 99999"
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm, resume_content=resume)

    await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert resume in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_job_title(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm)

    await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert sample_job["title"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_company(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm)

    await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert sample_job["company"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_candidate_skills(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm)

    await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert "Python" in llm.last_prompt
    assert "XGBoost" in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_includes_experience_docs_when_present(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm, experience_docs={"leadership": "Led a team of 5."})

    await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert "Led a team of 5." in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_notes_no_experience_docs_when_absent(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm, experience_docs={})

    await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert "No additional experience documents" in llm.last_prompt


@pytest.mark.asyncio
async def test_system_prompt_is_passed_to_llm(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm)

    await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert llm.last_system == TAILOR_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_system_prompt_prohibits_fabrication():
    assert "fabricat" in TAILOR_SYSTEM_PROMPT.lower() or "truthful" in TAILOR_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tailored_resume_key_returned(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm)

    result = await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert "tailored_resume" in result
    assert len(result["tailored_resume"]) > 0


@pytest.mark.asyncio
async def test_highlights_is_a_list(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = make_service(llm)

    result = await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert isinstance(result["highlights"], list)
    assert len(result["highlights"]) >= 1


@pytest.mark.asyncio
async def test_empty_llm_response_returns_empty_resume(sample_job, sample_profile):
    llm = MockLLMProvider(json_response={})
    service = make_service(llm)

    result = await service.tailor_resume(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert result["tailored_resume"] == ""
    assert result["highlights"] == []


# ---------------------------------------------------------------------------
# File I/O errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_raises_if_no_master_resume(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_TAILOR_RESPONSE)
    service = ResumeService(llm=llm)
    # Don't mock load_master_resume — let it try the real path (which won't exist in CI)
    service._profile_path = Path("/nonexistent/path/that/cannot/exist")

    with pytest.raises(FileNotFoundError):
        await service.tailor_resume(
            job_title=sample_job["title"],
            company=sample_job["company"],
            job_description=sample_job["description"],
            requirements=sample_job["requirements"],
            profile=sample_profile,
        )
