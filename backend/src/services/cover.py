"""Cover letter generation service."""

import logging
from pathlib import Path
from typing import Any, Literal

from .llm import LLMProvider, get_llm_provider
from ..config import get_settings

logger = logging.getLogger(__name__)

CoverLetterTone = Literal["professional", "enthusiastic", "casual"]

COVER_SYSTEM_PROMPT = """You are an expert cover letter writer who creates compelling, personalized cover letters.
Your letters are professional, engaging, and tailored to both the company culture and job requirements.
You highlight the candidate's relevant experience while showing genuine interest in the specific role.
Output clean, professional text ready to be used directly."""

COVER_USER_PROMPT = """Generate a professional cover letter for this job application.

## Candidate Profile:
Name: {name}
Target Titles: {target_titles}
Years of Experience: {experience_years}
Key Skills: {skills}

## Resume Summary:
{resume_summary}

## Job Details:
Title: {job_title}
Company: {company}
Location: {location}
Work Type: {work_type}

## Job Description:
{job_description}

## Requirements:
{requirements}
{template_instruction}
Please write a compelling cover letter that:
1. Opens with a hook that shows genuine interest in this specific role/company
2. Highlights 2-3 most relevant experiences or accomplishments
3. Demonstrates understanding of the role and how the candidate can contribute
4. Ends with a confident call to action
5. Maintains a {tone} tone throughout

The letter should be approximately 300-400 words.

Format response as JSON with keys: "cover_letter" (string) and "tone_used" (string)"""


class CoverLetterService:
    """Service for generating cover letters."""

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
        # Profile is sibling to data directory: backend/profile/
        return db_path.parent.parent / "profile"

    def load_template(self, template_name: str = "cover_letter_base") -> str | None:
        """Load a cover letter template if available.

        Args:
            template_name: Name of the template file (without .md extension).

        Returns:
            Template content or None if not found.
        """
        template_path = self._profile_path / "templates" / f"{template_name}.md"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return None

    def get_resume_summary(self) -> str:
        """Get a summary from the master resume for context.

        Returns:
            First portion of the resume or a fallback message.
        """
        resume_path = self._profile_path / "resume.md"
        if resume_path.exists():
            content = resume_path.read_text(encoding="utf-8")
            # Return first ~1000 chars as summary to provide enough context
            if len(content) > 1000:
                return content[:1000] + "..."
            return content
        return "Resume not available."

    async def generate_cover_letter(
        self,
        job_title: str,
        company: str,
        location: str | None,
        work_type: str | None,
        job_description: str,
        requirements: str | None,
        profile: dict[str, Any],
        tone: CoverLetterTone = "professional",
        template_name: str | None = None,
    ) -> dict[str, Any]:
        """Generate a cover letter for a specific job.

        Args:
            job_title: The job title.
            company: The company name.
            location: Job location (optional).
            work_type: Work type like 'remote', 'hybrid' (optional).
            job_description: Full job description text.
            requirements: Job requirements text (optional).
            profile: User profile dictionary with name, skills, etc.
            tone: Desired tone for the letter.
            template_name: Optional template to use as guidance.

        Returns:
            Dictionary with 'cover_letter' and 'tone_used' keys.
        """
        # Prepare template instruction if template exists
        template = self.load_template(template_name) if template_name else None
        template_instruction = ""
        if template:
            template_instruction = (
                f"\n## Template to follow (adapt as needed):\n{template}\n"
            )

        # Format skills from profile
        skills = profile.get("skills", {})
        skills_list = (
            skills.get("languages", [])
            + skills.get("ml_tools", [])
            + skills.get("platforms", [])
            + skills.get("other", [])
        )
        skills_text = ", ".join(skills_list) if skills_list else "See resume"

        prompt = COVER_USER_PROMPT.format(
            name=profile.get("name", "Candidate"),
            target_titles=", ".join(profile.get("target_titles", [])),
            experience_years=profile.get("experience_years", "N/A"),
            skills=skills_text,
            resume_summary=self.get_resume_summary(),
            job_title=job_title,
            company=company,
            location=location or "Not specified",
            work_type=work_type or "Not specified",
            job_description=job_description or "Not provided",
            requirements=requirements or "Not specified",
            template_instruction=template_instruction,
            tone=tone,
        )

        llm = self._get_llm()
        logger.info(f"Generating cover letter for {job_title} at {company}")
        result = await llm.complete_json(prompt, COVER_SYSTEM_PROMPT)

        return {
            "cover_letter": result.get("cover_letter", ""),
            "tone_used": result.get("tone_used", tone),
        }

    async def close(self) -> None:
        """Clean up resources."""
        if self.llm:
            await self.llm.close()
