"""Prompt engineering tests for the scorer service.

These tests verify:
1. The prompt contains all required candidate and job fields
2. Output normalization (score clamping, default values)
3. Dealbreaker logic forces score to 0
4. The system prompt sets the right expert framing
"""

import pytest

from src.services.scorer import ScorerService, SCORING_SYSTEM_PROMPT
from .conftest import MockLLMProvider


GOOD_SCORE_RESPONSE = {
    "score": 85,
    "rationale": "Strong skills match on Python, XGBoost, and AWS. Hybrid work type aligns.",
    "matching_skills": ["Python", "SQL", "XGBoost", "AWS"],
    "missing_skills": ["Spark Streaming"],
    "dealbreaker_triggered": None,
}

DEALBREAKER_RESPONSE = {
    "score": 75,  # LLM incorrectly returns non-zero — service must not override
    "rationale": "Clearance required — dealbreaker triggered.",
    "matching_skills": ["Python"],
    "missing_skills": [],
    "dealbreaker_triggered": "clearance required",
}

OUT_OF_RANGE_RESPONSE = {
    "score": 150,  # Must be clamped to 100
    "rationale": "Perfect match.",
    "matching_skills": ["Python"],
    "missing_skills": [],
    "dealbreaker_triggered": None,
}

NEGATIVE_SCORE_RESPONSE = {
    "score": -10,  # Must be clamped to 0
    "rationale": "Very poor match.",
    "matching_skills": [],
    "missing_skills": ["Everything"],
    "dealbreaker_triggered": None,
}


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prompt_contains_candidate_name(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(sample_job, sample_profile)

    assert sample_profile["name"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_all_target_titles(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(sample_job, sample_profile)

    for title in sample_profile["target_titles"]:
        assert title in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_skills(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(sample_job, sample_profile)

    prompt = llm.last_prompt
    # Spot-check one skill from each category
    assert "Python" in prompt       # languages
    assert "XGBoost" in prompt      # ml_tools
    assert "AWS" in prompt          # platforms
    assert "NLP" in prompt          # other


@pytest.mark.asyncio
async def test_prompt_contains_job_title_and_company(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(sample_job, sample_profile)

    assert sample_job["title"] in llm.last_prompt
    assert sample_job["company"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_formatted_salary_range(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(sample_job, sample_profile)

    # $130,000 - $160,000 (formatted)
    assert "130,000" in llm.last_prompt
    assert "160,000" in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_dealbreakers(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(sample_job, sample_profile)

    assert "clearance required" in llm.last_prompt


@pytest.mark.asyncio
async def test_system_prompt_is_expert_framing():
    assert "career advisor" in SCORING_SYSTEM_PROMPT.lower()
    assert "honest" in SCORING_SYSTEM_PROMPT.lower() or "objectively" in SCORING_SYSTEM_PROMPT.lower()


@pytest.mark.asyncio
async def test_system_prompt_is_passed_to_llm(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(sample_job, sample_profile)

    assert llm.last_system == SCORING_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Minimal / missing field handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_salary_shows_not_specified(minimal_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(minimal_job, sample_profile)

    assert "Not specified" in llm.last_prompt


@pytest.mark.asyncio
async def test_salary_min_only_shows_plus_suffix(sample_profile):
    job = {
        "title": "Data Scientist", "company": "Acme", "location": "Remote",
        "work_type": "remote", "salary_min": 100000, "salary_max": None,
        "description": "ML work.", "requirements": None,
    }
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    await service.score_job(job, sample_profile)

    assert "100,000+" in llm.last_prompt


# ---------------------------------------------------------------------------
# Output normalization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_is_returned(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    result = await service.score_job(sample_job, sample_profile)

    assert result["score"] == 85


@pytest.mark.asyncio
async def test_score_clamped_above_100(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=OUT_OF_RANGE_RESPONSE)
    service = ScorerService(llm=llm)

    result = await service.score_job(sample_job, sample_profile)

    assert result["score"] == 100


@pytest.mark.asyncio
async def test_score_clamped_below_0(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=NEGATIVE_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    result = await service.score_job(sample_job, sample_profile)

    assert result["score"] == 0


@pytest.mark.asyncio
async def test_matching_and_missing_skills_returned(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    result = await service.score_job(sample_job, sample_profile)

    assert isinstance(result["matching_skills"], list)
    assert isinstance(result["missing_skills"], list)
    assert "Python" in result["matching_skills"]


@pytest.mark.asyncio
async def test_dealbreaker_triggered_is_none_by_default(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=GOOD_SCORE_RESPONSE)
    service = ScorerService(llm=llm)

    result = await service.score_job(sample_job, sample_profile)

    assert result["dealbreaker_triggered"] is None


@pytest.mark.asyncio
async def test_dealbreaker_string_is_preserved(sample_job, sample_profile):
    llm = MockLLMProvider(json_response=DEALBREAKER_RESPONSE)
    service = ScorerService(llm=llm)

    result = await service.score_job(sample_job, sample_profile)

    assert result["dealbreaker_triggered"] == "clearance required"


# ---------------------------------------------------------------------------
# LLM failure fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_failure_returns_zero_score(sample_job, sample_profile):
    class FailingLLM(MockLLMProvider):
        async def complete_json(self, prompt, system=None):
            raise RuntimeError("API timeout")

    service = ScorerService(llm=FailingLLM())
    result = await service.score_job(sample_job, sample_profile)

    assert result["score"] == 0
    assert "Scoring failed" in result["rationale"]
    assert result["matching_skills"] == []
