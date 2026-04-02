"""Project matching service — maps portfolio projects to job requirements."""

import json
import logging
from pathlib import Path

from .llm import LLMProvider, get_llm_provider
from ..config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a career coach helping a data scientist/ML engineer prepare job applications.
Your job is to match their portfolio projects to a specific job's requirements and generate concrete talking points."""

USER_PROMPT = """Given this job and the candidate's portfolio, identify the 3-5 most relevant projects to highlight.

## Job
Title: {job_title}
Company: {company}
Description:
{job_description}

Requirements:
{requirements}

## Portfolio Projects
{projects_catalogue}

For each recommended project, provide:
1. Why it's relevant to THIS specific role
2. A STAR-format talking point (Situation/Task → Action → Result)
3. Which specific job requirements it addresses
4. Technical depth angle — what architectural or design decision to emphasize

Also provide:
- A "lead project" — the single strongest match to open with
- 2-3 skill gaps (things the JD emphasizes that the portfolio doesn't clearly demonstrate)
- How to reframe existing experience to address those gaps

Format as JSON with this structure:
{{
  "lead_project": "project name",
  "projects": [
    {{
      "name": "project name",
      "relevance": "why it fits this role",
      "star_story": "STAR format talking point",
      "addresses_requirements": ["req1", "req2"],
      "technical_angle": "architectural/design decision to emphasize"
    }}
  ],
  "skill_gaps": [
    {{
      "gap": "skill or experience gap",
      "reframe": "how to address this in the interview"
    }}
  ]
}}"""


class ProjectMatcherService:
    """Matches portfolio projects to job requirements."""

    def __init__(self, llm: LLMProvider | None = None):
        self.llm = llm

    def _get_llm(self) -> LLMProvider:
        if self.llm is None:
            self.llm = get_llm_provider()
        return self.llm

    def _load_projects_catalogue(self) -> str:
        """Load the projects catalogue from backend/data/projects.md."""
        settings = get_settings()
        catalogue_path = Path(settings.database_path).parent / "projects.md"
        if catalogue_path.exists():
            return catalogue_path.read_text(encoding="utf-8")
        return "No projects catalogue found. Create backend/data/projects.md."

    async def match_projects(
        self,
        job_title: str,
        company: str,
        job_description: str,
        requirements: str | None,
    ) -> dict:
        """Match portfolio projects to a job's requirements.

        Returns dict with lead_project, projects list, and skill_gaps.
        """
        catalogue = self._load_projects_catalogue()
        prompt = USER_PROMPT.format(
            job_title=job_title,
            company=company,
            job_description=job_description or "Not provided",
            requirements=requirements or "Not specified",
            projects_catalogue=catalogue,
        )

        llm = self._get_llm()
        logger.info(f"Matching projects for {job_title} at {company}")
        result = await llm.complete_json(prompt, SYSTEM_PROMPT)
        return result

    async def close(self) -> None:
        if self.llm:
            await self.llm.close()
