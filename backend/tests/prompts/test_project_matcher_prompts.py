"""Prompt engineering tests for the project matcher service.

These tests verify:
1. Job details reach the prompt
2. Projects catalogue content is included
3. Output structure matches the schema (lead_project, projects, skill_gaps)
4. Each project has required subfields
5. Skill gaps have required subfields
"""

import pytest
from pathlib import Path

from src.services.project_matcher import ProjectMatcherService, SYSTEM_PROMPT
from .conftest import MockLLMProvider


SAMPLE_CATALOGUE = """
## Canopy
Personal job search assistant. Stack: Python, Litestar, SQLite, React.
Built scrapers, LLM-based scoring, vector search.

## Banyan
Fraud detection system for financial transactions. Stack: Python, XGBoost, AWS SageMaker.
Achieved 94% precision at 2% false positive rate.

## Maple
NLP pipeline for scientific literature classification. Stack: PyTorch, HuggingFace.
"""

GOOD_MATCH_RESPONSE = {
    "lead_project": "Banyan",
    "projects": [
        {
            "name": "Banyan",
            "relevance": "Directly mirrors USAA's fraud detection ML work",
            "star_story": "S: Financial transactions needed real-time fraud scoring. T: Build low-latency model. A: Deployed XGBoost with SageMaker. R: 94% precision at 2% FPR.",
            "addresses_requirements": ["XGBoost", "AWS", "5+ years experience"],
            "technical_angle": "Feature engineering for imbalanced classes",
        },
        {
            "name": "Maple",
            "relevance": "Demonstrates NLP and PyTorch proficiency",
            "star_story": "S: Thousands of papers needed categorization. T: Build classifier. A: Fine-tuned BERT. R: 94% F1.",
            "addresses_requirements": ["Python", "ML frameworks"],
            "technical_angle": "Transfer learning trade-offs",
        },
    ],
    "skill_gaps": [
        {
            "gap": "No explicit Apache Spark streaming experience",
            "reframe": "Highlight Spark batch work on Maple and willingness to extend to streaming",
        }
    ],
}


def make_service(llm: MockLLMProvider, catalogue: str = SAMPLE_CATALOGUE) -> ProjectMatcherService:
    service = ProjectMatcherService(llm=llm)
    service._load_projects_catalogue = lambda: catalogue
    return service


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prompt_contains_job_title(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    assert sample_job["title"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_company(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    assert sample_job["company"] in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_contains_job_description(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    # Unique phrase from the sample description
    assert "fraud" in llm.last_prompt.lower()


@pytest.mark.asyncio
async def test_prompt_contains_projects_catalogue(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    assert "Banyan" in llm.last_prompt
    assert "Maple" in llm.last_prompt


@pytest.mark.asyncio
async def test_prompt_requests_star_format(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    assert "STAR" in llm.last_prompt


@pytest.mark.asyncio
async def test_system_prompt_passed_to_llm(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    assert llm.last_system == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_missing_requirements_falls_back_gracefully(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=None,
    )

    assert "Not specified" in llm.last_prompt


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_has_lead_project(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    result = await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    assert "lead_project" in result
    assert isinstance(result["lead_project"], str)


@pytest.mark.asyncio
async def test_result_projects_is_list(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    result = await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    assert isinstance(result["projects"], list)
    assert len(result["projects"]) >= 1


@pytest.mark.asyncio
async def test_each_project_has_required_fields(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    result = await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    required_fields = {"name", "relevance", "star_story", "addresses_requirements", "technical_angle"}
    for project in result["projects"]:
        missing = required_fields - set(project.keys())
        assert not missing, f"Project missing fields: {missing}"


@pytest.mark.asyncio
async def test_skill_gaps_is_list(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    result = await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    assert isinstance(result["skill_gaps"], list)


@pytest.mark.asyncio
async def test_each_skill_gap_has_gap_and_reframe(sample_job):
    llm = MockLLMProvider(json_response=GOOD_MATCH_RESPONSE)
    service = make_service(llm)

    result = await service.match_projects(
        job_title=sample_job["title"],
        company=sample_job["company"],
        job_description=sample_job["description"],
        requirements=sample_job["requirements"],
    )

    for gap in result["skill_gaps"]:
        assert "gap" in gap, "skill_gap missing 'gap' field"
        assert "reframe" in gap, "skill_gap missing 'reframe' field"
