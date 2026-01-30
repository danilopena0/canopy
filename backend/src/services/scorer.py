"""Job fit scoring service using LLM."""

import json
import logging
from pathlib import Path
from typing import Any

from ..config import get_settings
from .llm import LLMProvider, get_llm_provider

logger = logging.getLogger(__name__)

SCORING_SYSTEM_PROMPT = """You are an expert career advisor who evaluates job fit for candidates.
Your goal is to objectively assess how well a job matches a candidate's profile.
Be honest and precise - don't inflate scores. A perfect match is rare.
Consider both hard requirements and soft preferences."""

SCORING_USER_PROMPT = """Evaluate how well this job matches the candidate's profile.

## Candidate Profile:
- Name: {name}
- Target Titles: {target_titles}
- Years of Experience: {experience_years}
- Skills:
  - Languages: {languages}
  - ML Tools: {ml_tools}
  - Platforms: {platforms}
  - Other: {other_skills}
- Preferred Locations: {locations}
- Preferred Work Types: {work_types}
- Preferred Industries: {industries}
- Minimum Salary: {min_salary}
- Dealbreakers: {dealbreakers}

## Job Posting:
- Title: {job_title}
- Company: {company}
- Location: {location}
- Work Type: {work_type}
- Salary Range: {salary_range}
- Description: {description}
- Requirements: {requirements}

## Scoring Rubric (100 points total):
1. Title Match (25 pts): How well does the job title align with target titles?
2. Skills Match (35 pts): How many required skills does the candidate have?
3. Location/Work Type (15 pts): Does location and work arrangement fit preferences?
4. Salary Fit (10 pts): Is the salary within acceptable range?
5. Experience Level (10 pts): Does the experience level requirement match?
6. Industry Preference (5 pts bonus): Is this in a preferred industry?

## Dealbreaker Check:
If ANY dealbreaker is triggered, score MUST be 0.

Provide your evaluation as JSON with these exact keys:
- "score": integer 0-100
- "rationale": string explaining the score (2-3 sentences)
- "matching_skills": array of skills the candidate has that match requirements
- "missing_skills": array of required skills the candidate lacks
- "dealbreaker_triggered": null if none, or string describing which dealbreaker was hit"""


class ScorerService:
    """Service for scoring job fit using LLM."""

    def __init__(self, llm: LLMProvider | None = None):
        self.llm = llm
        self._profile_path = self._get_profile_path()

    def _get_llm(self) -> LLMProvider:
        """Get or create the LLM provider."""
        if self.llm is None:
            self.llm = get_llm_provider()
        return self.llm

    def _get_profile_path(self) -> Path:
        """Get the profile directory path."""
        settings = get_settings()
        db_path = Path(settings.database_path)
        return db_path.parent / "profile.json"

    def load_profile(self) -> dict[str, Any]:
        """Load user profile from file.

        Returns:
            User profile dictionary.

        Raises:
            FileNotFoundError: If profile doesn't exist.
        """
        if not self._profile_path.exists():
            raise FileNotFoundError(
                f"Profile not found at {self._profile_path}. "
                "Please create backend/data/profile.json with your profile."
            )
        with open(self._profile_path) as f:
            return json.load(f)

    async def score_job(
        self,
        job: dict[str, Any],
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Score a job against the user's profile.

        Args:
            job: Job data dictionary with title, company, description, etc.
            profile: Optional profile dict. Loads from file if not provided.

        Returns:
            Dictionary with score, rationale, matching_skills, missing_skills,
            and dealbreaker_triggered keys.
        """
        if profile is None:
            profile = self.load_profile()

        # Extract skills from profile
        skills = profile.get("skills", {})
        languages = ", ".join(skills.get("languages", [])) or "Not specified"
        ml_tools = ", ".join(skills.get("ml_tools", [])) or "Not specified"
        platforms = ", ".join(skills.get("platforms", [])) or "Not specified"
        other_skills = ", ".join(skills.get("other", [])) or "Not specified"

        # Format salary range
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        if salary_min and salary_max:
            salary_range = f"${salary_min:,} - ${salary_max:,}"
        elif salary_min:
            salary_range = f"${salary_min:,}+"
        elif salary_max:
            salary_range = f"Up to ${salary_max:,}"
        else:
            salary_range = "Not specified"

        # Format min salary from profile
        min_salary = profile.get("min_salary")
        min_salary_str = f"${min_salary:,}" if min_salary else "Not specified"

        prompt = SCORING_USER_PROMPT.format(
            name=profile.get("name", "Candidate"),
            target_titles=", ".join(profile.get("target_titles", [])) or "Any",
            experience_years=profile.get("experience_years", "Not specified"),
            languages=languages,
            ml_tools=ml_tools,
            platforms=platforms,
            other_skills=other_skills,
            locations=", ".join(profile.get("locations", [])) or "Any",
            work_types=", ".join(profile.get("work_types", [])) or "Any",
            industries=", ".join(profile.get("industries", [])) or "Any",
            min_salary=min_salary_str,
            dealbreakers=", ".join(profile.get("dealbreakers", [])) or "None",
            job_title=job.get("title", "Unknown"),
            company=job.get("company", "Unknown"),
            location=job.get("location") or "Not specified",
            work_type=job.get("work_type") or "Not specified",
            salary_range=salary_range,
            description=job.get("description") or "Not provided",
            requirements=job.get("requirements") or "Not specified",
        )

        llm = self._get_llm()
        logger.info(f"Scoring job: {job.get('title')} at {job.get('company')}")

        try:
            result = await llm.complete_json(prompt, SCORING_SYSTEM_PROMPT)
        except Exception as e:
            logger.error(f"LLM scoring failed: {e}")
            # Return a default failed result
            return {
                "score": 0,
                "rationale": f"Scoring failed: {str(e)}",
                "matching_skills": [],
                "missing_skills": [],
                "dealbreaker_triggered": None,
            }

        # Validate and normalize the response
        return {
            "score": min(100, max(0, int(result.get("score", 0)))),
            "rationale": result.get("rationale", "No rationale provided"),
            "matching_skills": result.get("matching_skills", []),
            "missing_skills": result.get("missing_skills", []),
            "dealbreaker_triggered": result.get("dealbreaker_triggered"),
        }

    async def close(self) -> None:
        """Clean up resources."""
        if self.llm:
            await self.llm.close()
