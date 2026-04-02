#!/usr/bin/env python3
"""Generate interview prep materials with Mermaid diagrams.

Creates a markdown document with:
- Key technical topics the JD signals they care about
- Mermaid diagrams for data flows and architecture relevant to your background
- STAR stories for behavioral questions
- Questions to ask the interviewer
- Architectural decisions from your projects to discuss

Output saved to: backend/profile/applications/{job_id}/interview_prep.md

Usage:
    python scripts/interview_prep.py <job_id>
    python scripts/interview_prep.py --list
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db import Database
from src.services.llm import get_llm_provider

SYSTEM_PROMPT = """You are a technical interview coach specializing in data science and ML engineering roles.
You create thorough, specific interview prep materials tailored to the exact job and the candidate's background.
Your Mermaid diagrams are syntactically correct and render cleanly in markdown viewers."""

USER_PROMPT = """Create comprehensive interview prep materials for this candidate and job.

## Job
Title: {job_title}
Company: {company}
Description:
{job_description}

Requirements:
{requirements}

## Candidate Resume Summary
{resume_summary}

## Portfolio Projects
{projects_catalogue}

Generate a complete interview prep document in markdown. Include:

### 1. Role Intelligence (2-3 paragraphs)
- What this role actually does day-to-day based on the JD
- What the team likely looks like and the candidate's position in it
- Key success metrics they'll be evaluated on in the first 90 days

### 2. Technical Topics to Prepare
List 6-8 technical areas the JD signals they care about, with:
- Depth level expected (surface / working / deep)
- 1-2 likely interview questions per topic
- Key points to cover in your answer

### 3. Mermaid Diagrams
Create 3-4 Mermaid diagrams that:
a) Illustrate a data flow or ML pipeline architecture relevant to this role
b) Show an architecture decision you made in one of your projects (pick the most relevant)
c) A system design you could propose for a common problem in this domain
d) Any other diagram useful for communicating your technical background

Each diagram must:
- Be valid Mermaid syntax (use ```mermaid fenced blocks)
- Have a clear title and brief explanation (2-3 sentences) before/after it
- Be something you could walk through in a technical interview

Prefer: flowchart TD, sequenceDiagram, or graph LR for clarity.
Avoid: complex stateDiagram or gitGraph that may not render cleanly.

### 4. STAR Stories (Behavioral)
Prepare 4-5 STAR stories mapped to common behavioral questions:
- Tell me about a time you dealt with ambiguous requirements
- Describe a project where you had to make a key technical trade-off
- Tell me about a time you had to communicate technical findings to non-technical stakeholders
- Describe a failure or mistake and what you learned
- Tell me about your most technically challenging project

For each, reference a specific project from the portfolio.

### 5. Questions to Ask Them
8-10 thoughtful questions that signal strategic thinking:
- About the data and infrastructure
- About the team and workflow
- About success criteria and growth
- About technical challenges they're currently facing

### 6. Salary & Negotiation Notes
Based on the role, level, and location:
- Expected range and how to anchor
- What benefits/perks to probe for
- When to bring up competing offers

Format the entire response as a single clean markdown document.
Use proper headers (##, ###), bullet lists, and code blocks for Mermaid diagrams."""


async def generate_prep(job_id: str) -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
    await db.disconnect()

    if not row:
        print(f"Job not found: {job_id}")
        print("Run: python scripts/get_job.py --list")
        sys.exit(1)

    job = dict(row)

    print(f"\nGenerating interview prep for:")
    print(f"  {job['title']} at {job['company']}\n")

    # Load resume
    profile_dir = Path(settings.database_path).parent.parent / "profile"
    resume_path = profile_dir / "resume.md"
    if resume_path.exists():
        resume_text = resume_path.read_text(encoding="utf-8")
        # Give full resume for richer context, truncate at 4000 chars
        resume_summary = resume_text[:4000] + ("..." if len(resume_text) > 4000 else "")
    else:
        resume_summary = "Resume not available at backend/profile/resume.md"

    # Load projects catalogue
    catalogue_path = Path(settings.database_path).parent / "projects.md"
    if catalogue_path.exists():
        projects_catalogue = catalogue_path.read_text(encoding="utf-8")
    else:
        projects_catalogue = "Projects catalogue not found at backend/data/projects.md"

    prompt = USER_PROMPT.format(
        job_title=job["title"],
        company=job["company"],
        job_description=job.get("description", "Not provided")[:4000],
        requirements=job.get("requirements", "Not provided")[:2000],
        resume_summary=resume_summary,
        projects_catalogue=projects_catalogue,
    )

    print("Generating with LLM (this may take 30-60 seconds)...")
    llm = get_llm_provider()
    try:
        content = await llm.complete(prompt, SYSTEM_PROMPT)
    finally:
        await llm.close()

    # Save to applications directory
    out_dir = profile_dir / "applications" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "interview_prep.md"
    out_path.write_text(content, encoding="utf-8")

    size = out_path.stat().st_size
    print(f"\nSaved: {out_path}")
    print(f"Size: {size:,} bytes")
    print(f"\nOpen in PyCharm for Mermaid diagram rendering.")
    print(f"Enable: Settings → Plugins → Mermaid  (if not already)")


async def list_jobs() -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()
    rows = await db.fetchall(
        "SELECT id, title, company, fit_score FROM jobs ORDER BY scraped_at DESC LIMIT 20"
    )
    await db.disconnect()

    print(f"\n{'ID':<18} {'Score':>5}  Title")
    print("-" * 60)
    for r in rows:
        score = f"{r['fit_score']:.0f}" if r["fit_score"] else "  —"
        print(f"{r['id']:<18} {score:>5}  {r['title']} @ {r['company']}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        asyncio.run(list_jobs())
        sys.exit(0)

    asyncio.run(generate_prep(sys.argv[1]))
