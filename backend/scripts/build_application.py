#!/usr/bin/env python3
"""Build a full application package for a job.

Generates tailored resume, cover letter, and project highlights.
Output saved to: backend/profile/applications/{job_id}/

Usage:
    python scripts/build_application.py <job_id>
    python scripts/build_application.py <job_id> --tone enthusiastic
    python scripts/build_application.py --list   # show recent jobs
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db import Database
from src.services.resume import ResumeService
from src.services.cover import CoverLetterService
from src.services.project_matcher import ProjectMatcherService


def get_output_dir(job_id: str) -> Path:
    settings = get_settings()
    profile_dir = Path(settings.database_path).parent.parent / "profile"
    out = profile_dir / "applications" / job_id
    out.mkdir(parents=True, exist_ok=True)
    return out


async def build(job_id: str, tone: str = "professional") -> None:
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
    out_dir = get_output_dir(job_id)

    print(f"\nBuilding application package for:")
    print(f"  {job['title']} at {job['company']}")
    print(f"  Output: {out_dir}\n")

    # Load profile
    profile_path = Path(settings.database_path).parent / "profile.json"
    profile = {}
    if profile_path.exists():
        with open(profile_path) as f:
            profile = json.load(f)

    # --- 1. Tailored Resume ---
    print("1/3  Tailoring resume...")
    resume_service = ResumeService()
    if resume_service.has_resume():
        resume_result = await resume_service.tailor_resume(
            job_title=job["title"],
            company=job["company"],
            job_description=job.get("description", ""),
            requirements=job.get("requirements"),
        )
        resume_path = out_dir / "resume_tailored.md"
        resume_path.write_text(resume_result.get("tailored_resume", ""), encoding="utf-8")

        highlights = resume_result.get("highlights", [])
        highlights_text = "\n".join(f"- {h}" for h in highlights)
        print(f"     Saved: {resume_path.name}")
        print(f"     Highlights: {len(highlights)} items")
    else:
        print("     SKIPPED — no master resume found at backend/profile/resume.md")
        highlights_text = ""
    await resume_service.close()

    # --- 2. Cover Letter ---
    print("2/3  Generating cover letter...")
    cover_service = CoverLetterService()
    cover_result = await cover_service.generate_cover_letter(
        job_title=job["title"],
        company=job["company"],
        location=job.get("location"),
        work_type=job.get("work_type"),
        job_description=job.get("description", ""),
        requirements=job.get("requirements"),
        profile=profile,
    )
    await cover_service.close()

    cover_path = out_dir / "cover_letter.md"
    cover_path.write_text(cover_result.get("cover_letter", ""), encoding="utf-8")
    print(f"     Saved: {cover_path.name}")

    # --- 3. Project Highlights ---
    print("3/3  Matching portfolio projects...")
    matcher = ProjectMatcherService()
    match_result = await matcher.match_projects(
        job_title=job["title"],
        company=job["company"],
        job_description=job.get("description", ""),
        requirements=job.get("requirements"),
    )
    await matcher.close()

    projects_md = _format_project_highlights(match_result, job)
    projects_path = out_dir / "project_highlights.md"
    projects_path.write_text(projects_md, encoding="utf-8")
    print(f"     Saved: {projects_path.name}")
    print(f"     Lead project: {match_result.get('lead_project', 'N/A')}")

    # --- Summary ---
    summary = _build_summary(job, match_result, highlights_text, out_dir)
    summary_path = out_dir / "README.md"
    summary_path.write_text(summary, encoding="utf-8")

    print(f"\nDone. Files in {out_dir}:")
    for f in sorted(out_dir.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name:<30} {size:>6} bytes")

    print(f"\nNext step — interview prep:")
    print(f"  python scripts/interview_prep.py {job_id}")


def _format_project_highlights(match_result: dict, job: dict) -> str:
    lead = match_result.get("lead_project", "")
    projects = match_result.get("projects", [])
    gaps = match_result.get("skill_gaps", [])

    lines = [
        f"# Project Highlights",
        f"## {job['title']} at {job['company']}",
        "",
        f"**Lead project to open with:** {lead}",
        "",
        "---",
        "",
        "## Recommended Projects",
        "",
    ]

    for i, p in enumerate(projects, 1):
        lines += [
            f"### {i}. {p.get('name', 'Unknown')}",
            "",
            f"**Why it's relevant:** {p.get('relevance', '')}",
            "",
            f"**STAR Talking Point:**",
            f"> {p.get('star_story', '')}",
            "",
            f"**Addresses:** {', '.join(p.get('addresses_requirements', []))}",
            "",
            f"**Technical angle to emphasize:** {p.get('technical_angle', '')}",
            "",
        ]

    if gaps:
        lines += ["---", "", "## Skill Gaps & Reframes", ""]
        for g in gaps:
            lines += [
                f"**Gap:** {g.get('gap', '')}",
                f"**Reframe:** {g.get('reframe', '')}",
                "",
            ]

    return "\n".join(lines)


def _build_summary(job: dict, match_result: dict, highlights: str, out_dir: Path) -> str:
    return f"""# Application Package
## {job['title']} at {job['company']}

**Job ID:** {job['id']}
**URL:** {job.get('url', 'N/A')}
**Location:** {job.get('location', 'N/A')}  |  **Type:** {job.get('work_type', 'N/A')}
**Fit Score:** {job.get('fit_score', 'Not scored')}

## Files
| File | Purpose |
|------|---------|
| `resume_tailored.md` | Resume tailored to this specific JD |
| `cover_letter.md` | Cover letter ready to send |
| `project_highlights.md` | Which projects to bring up and how |
| `interview_prep.md` | Interview prep with diagrams (run interview_prep.py) |

## Resume Highlights
{highlights or '_(run build_application.py to generate)_'}

## Lead Project
{match_result.get('lead_project', 'N/A')}
"""


async def list_jobs() -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()
    rows = await db.fetchall(
        """SELECT id, title, company, fit_score, status
           FROM jobs ORDER BY scraped_at DESC LIMIT 20"""
    )
    await db.disconnect()

    print(f"\n{'ID':<18} {'Score':>5}  {'Status':<10}  {'Title'}")
    print("-" * 70)
    for r in rows:
        score = f"{r['fit_score']:.0f}" if r["fit_score"] else "  —"
        print(f"{r['id']:<18} {score:>5}  {r['status']:<10}  {r['title']} @ {r['company']}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        asyncio.run(list_jobs())
        sys.exit(0)

    job_id = sys.argv[1]
    tone = "professional"
    if "--tone" in sys.argv:
        idx = sys.argv.index("--tone")
        if idx + 1 < len(sys.argv):
            tone = sys.argv[idx + 1]

    asyncio.run(build(job_id, tone=tone))
