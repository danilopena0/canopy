"""Prompt engineering tests for the cover letter service.

These tests verify:
1. The prompt contains required job and candidate fields
2. The system prompt frames the correct persona
3. Word count guidance is present in the prompt
4. Output structure is correctly returned
5. Optional fields (requirements, template) degrade gracefully
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.services.cover import CoverLetterService, COVER_SYSTEM_PROMPT
from .conftest import MockLLMProvider


GOOD_COVER_RESPONSE = {
    "cover_letter": (
        "Dear Hiring Manager,\n\n"
        "I am excited to apply for the Senior Data Scientist position at USAA. "
        "With six years of experience building ML models in financial services, "
        "including fraud detection systems that reduced false positives by 30%, "
        "I am well prepared to contribute to your analytics team.\n\n"
        "Sincerely,\nAlex Rivera"
    ),
    "tone_used": "professional",
}


def make_service(llm: MockLLMProvider, resume_content: str = "Test resume content.") -> CoverLetterService:
    """Create a CoverLetterService with mocked file I/O."""
    service = CoverLetterService(llm=llm)
    # Patch resume loading so tests don't need actual files
    service.get_resume_summary = lambda: resume_content
    service.load_template = lambda name=None: None
    return service


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prompt_contains_job_title(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert sample_job["title"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_company_name(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert sample_job["company"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_candidate_name(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert sample_profile["name"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_word_count_guidance(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    # Prompt should instruct approximate length
    assert "300" in llm.last_prompt or "400" in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_resume_summary(sample_job, sample_profile):
    resume_snippet = "Unique resume content 12345"
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm, resume_content=resume_snippet)

    await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert resume_snippet in llm.last_prompt


@pytest.mark.asyncio
async def test_system_prompt_is_passed_to_llm(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert llm.last_system == COVER_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_system_prompt_emphasizes_personalization():
    assert "personalized" in COVER_SYSTEM_PROMPT.lower() or "tailored" in COVER_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Graceful degradation with missing optional fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_requirements_falls_back_to_not_specified(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=None,
        work_type=None,
        job_description=sample_job["description"],
        requirements=None,
        profile=sample_profile,
    )

    assert "Not specified" in llm.last_prompt


@pytest.mark.asyncio
async def test_no_template_skips_template_section(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
        template_name=None,
    )

    # No template section should be injected
    assert "Template to follow" not in llm.last_prompt


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cover_letter_key_returned(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    result = await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert "cover_letter" in result
    assert len(result["cover_letter"]) > 0


@pytest.mark.asyncio
async def test_tone_used_key_returned(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_COVER_RESPONSE)
    service = make_service(llm)

    result = await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert "tone_used" in result
    assert isinstance(result["tone_used"], str)


@pytest.mark.asyncio
async def test_empty_llm_response_returns_empty_cover_letter(sample_job, sample_profile):
    llm = MockLLMProvider(json_response={})  # LLM returns nothing useful
    service = make_service(llm)

    result = await service.generate_cover_letter(
        job_title=sample_job["title"],
        company=sample_job["company"],
        location=sample_job["location"],
        work_type=sample_job["work_type"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
        profile=sample_profile,
    )

    assert result["cover_letter"] == ""
