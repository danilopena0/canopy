"""Resume tailoring service."""

import logging
from pathlib import Path
from typing import Any

from .llm import LLMProvider, get_llm_provider
from ..config import get_settings

logger = logging.getLogger(__name__)

TAILOR_SYSTEM_PROMPT = """You are an expert resume writer who tailors resumes for specific job applications.
Your goal is to emphasize relevant experience, skills, and accomplishments that match the job requirements.
Maintain truthfulness - only reframe existing experience, never fabricate.
Output the tailored resume in clean markdown format."""

TAILOR_USER_PROMPT = """Given the following master resume and job description, create a tailored resume that:
1. Emphasizes skills and experience most relevant to this specific role
2. Reorders bullet points to prioritize the most relevant accomplishments
3. Uses keywords from the job description where naturally appropriate
4. Keeps the core truthful content while optimizing presentation

## Master Resume:
{master_resume}

## Additional Experience Documents:
{experience_docs}

## User Profile:
Name: {name}
Target Titles: {target_titles}
Years of Experience: {experience_years}
Key Skills: {skills}

## Job Title: {job_title}
## Company: {company}
## Job Description:
{job_description}

## Job Requirements:
{requirements}

Please provide:
1. The tailored resume in markdown format
2. A list of 3-5 key highlights you emphasized for this role

Format your response as JSON with keys: "tailored_resume" (string) and "highlights" (array of strings)"""


class ResumeService:
    """Service for loading, tailoring, and managing resumes."""

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

    def load_master_resume(self) -> str:
        """Load the master resume from file.

        Returns:
            The master resume content as a string.

        Raises:
            FileNotFoundError: If master resume doesn't exist.
        """
        resume_path = self._profile_path / "resume.md"
        if not resume_path.exists():
            raise FileNotFoundError(
                f"Master resume not found at {resume_path}. "
                "Please create backend/profile/resume.md with your resume content."
            )
        return resume_path.read_text(encoding="utf-8")

    def load_experience_documents(self) -> dict[str, str]:
        """Load all experience documents from the experience directory.

        Returns:
            Dictionary mapping filename (without extension) to content.
        """
        experience_dir = self._profile_path / "experience"
        if not experience_dir.exists():
            return {}

        docs = {}
        for path in experience_dir.glob("*.md"):
            docs[path.stem] = path.read_text(encoding="utf-8")
        return docs

    def has_resume(self) -> bool:
        """Check if a master resume exists."""
        resume_path = self._profile_path / "resume.md"
        return resume_path.exists()

    def list_documents(self) -> list[dict[str, Any]]:
        """List all available documents in the profile directory.

        Returns:
            List of document metadata dictionaries.
        """
        documents = []

        # Check master resume
        resume_path = self._profile_path / "resume.md"
        if resume_path.exists():
            stat = resume_path.stat()
            documents.append({
                "filename": "resume.md",
                "path": "resume.md",
                "size_bytes": stat.st_size,
                "doc_type": "resume",
            })

        # Check experience documents
        experience_dir = self._profile_path / "experience"
        if experience_dir.exists():
            for path in experience_dir.glob("*.md"):
                stat = path.stat()
                documents.append({
                    "filename": path.name,
                    "path": f"experience/{path.name}",
                    "size_bytes": stat.st_size,
                    "doc_type": "experience",
                })

        # Check templates
        templates_dir = self._profile_path / "templates"
        if templates_dir.exists():
            for path in templates_dir.glob("*.md"):
                stat = path.stat()
                documents.append({
                    "filename": path.name,
                    "path": f"templates/{path.name}",
                    "size_bytes": stat.st_size,
                    "doc_type": "template",
                })

        return documents

    async def tailor_resume(
        self,
        job_title: str,
        company: str,
        job_description: str,
        requirements: str | None,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a tailored resume for a specific job.

        Args:
            job_title: The job title.
            company: The company name.
            job_description: Full job description text.
            requirements: Job requirements text (optional).
            profile: User profile dictionary with skills, experience, etc.

        Returns:
            Dictionary with 'tailored_resume' and 'highlights' keys.

        Raises:
            FileNotFoundError: If master resume doesn't exist.
        """
        master_resume = self.load_master_resume()
        experience_docs = self.load_experience_documents()

        # Format experience docs for prompt
        if experience_docs:
            exp_text = "\n\n".join(
                f"### {name}\n{content}"
                for name, content in experience_docs.items()
            )
        else:
            exp_text = "No additional experience documents provided."

        # Format skills from profile
        skills = profile.get("skills", {})
        skills_list = (
            skills.get("languages", [])
            + skills.get("ml_tools", [])
            + skills.get("platforms", [])
            + skills.get("other", [])
        )
        skills_text = ", ".join(skills_list) if skills_list else "See resume"

        prompt = TAILOR_USER_PROMPT.format(
            master_resume=master_resume,
            experience_docs=exp_text,
            name=profile.get("name", ""),
            target_titles=", ".join(profile.get("target_titles", [])),
            experience_years=profile.get("experience_years", "Not specified"),
            skills=skills_text,
            job_title=job_title,
            company=company,
            job_description=job_description or "Not provided",
            requirements=requirements or "Not specified",
        )

        llm = self._get_llm()
        logger.info(f"Tailoring resume for {job_title} at {company}")
        result = await llm.complete_json(prompt, TAILOR_SYSTEM_PROMPT)

        return {
            "tailored_resume": result.get("tailored_resume", ""),
            "highlights": result.get("highlights", []),
        }

    async def close(self) -> None:
        """Clean up resources."""
        if self.llm:
            await self.llm.close()
