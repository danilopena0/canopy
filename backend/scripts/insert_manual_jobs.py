#!/usr/bin/env python3
"""Insert manually pasted job postings into the database and score them."""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db import Database

JOBS = [
    {
        "url": "https://www.indeed.com/viewjob?jk=strg-data-engineer-2026",
        "source": "manual",
        "title": "Data Engineer",
        "company": "South Texas Radiology Group, P.A.",
        "location": "San Antonio, TX",
        "work_type": "onsite",
        "salary_min": None,
        "salary_max": None,
        "posted_date": None,
        "description": """The Data Engineer is responsible for collecting, managing, and converting data into accessible information for business teams and analysts. Creates and maintains data pipelines that transfer data from various sources to a central data warehouse, and supports business functions that require analyzing this data. Performs data integrity review in conjunction with end users.

Job Responsibilities:
- Gathers information for moderately complex processes, analyzes data and trends, and identifies root causes.
- Create and maintain the infrastructure for a centralized data store in the form of a data warehouse, including selecting the best platform(s) for each component of the data warehouse; import data from various agency EHRs and web-based sources using ELT/ETL best practices.
- Work with internal managers and external partners to set up data pipelines to the data warehouse for reporting and other business functions; ensure data integrity of records for data sources including integrated information systems.
- Works with the President related to reporting needs for physician productivity and other measurables. Works with the Vice President, as needed, related to physician scheduling & reporting needs.
- Provide support for creation of enterprise reports using warehouse data, including the creation of a data dictionary.
- Maintain a data normalization strategy for new data coming into the data warehouse; create & maintain a semantic layer for developing report KPIs and business metrics.
- Assists with data mining and analytical capability to support decision making and corporate strategy.
- Maintain best practices for CI/CD of accurate and accessible business data using Agile project management principles.
- Review & audit reports, data sources and data streams for accuracy and completeness.
- Manage and deploy BI tools for use by various company teams.
- Maintain strict confidentiality of patient protected health information as mandated by STRG procedures and HIPAA Privacy, Security, HITECH regulations.""",
        "requirements": """Experience / Skill Requirements:
- Strong attention to detail and ability to multitask multiple priorities
- Advanced knowledge and experience in Excel required
- Knowledge of analytical and BI tools (MS Excel, Tableau, PowerBI)
- Strong programming skills (Python, SQL, shell/bash) and expertise in database technologies, ELT/ETL processes, REST APIs, data warehousing, and workflow management tools
- Experience querying and maintaining relational databases (SQL Server, Postgres) and version controlling (Github)
- Knowledge of containerization technologies, cloud development platforms such as GCP, and cloud-native applications
- Cursory understanding of healthcare terminology, including CPT, RVU and charge terminology
- Knowledge of revenue cycle systems and mapping logic within billing tables
- 4 years of experience in end-to-end analysis and/or operations experience

Education: Bachelor's degree in Computer Science, Data Analytics, Management Information Systems or Business Administration.
Work Schedule: Monday through Friday, on-site in San Antonio, TX 78230.""",
    },
    {
        "url": "https://www.indeed.com/viewjob?jk=strg-clinical-data-analyst-2026",
        "source": "manual",
        "title": "Clinical Data Analyst",
        "company": "South Texas Radiology Group, P.A.",
        "location": "San Antonio, TX",
        "work_type": "onsite",
        "salary_min": None,
        "salary_max": None,
        "posted_date": None,
        "description": """Focuses on analyzing clinical and operational data to improve workflow efficiency and overall performance. Provides analytical support for clinical operations across STRG. Position requires prior data analytics experience and radiology/clinical background.

Job Responsibilities:
- Develop and maintain dashboards that track Relative Value Units (RVUs) and sub-specialty workloads
- Identify trends, anomalies and opportunities for operational improvement
- Monitor key performance indicators (KPIs) and quality metrics
- Ensure data integrity, accuracy and consistency across systems
- Collect, analyze and interpret data from radiology systems including RIS, PACS and EHR
- Identify workflow inefficiencies and collaborates with physicians to implement solutions
- Complete data analysis related to scheduling, staffing, procedure volumes and turnaround times
- Perform ad hoc analyses to support clinical operations and business decisions
- Prepares materials for clinical meetings, captures action items, and ensures follow-through
- Translate complex data findings into clear, actionable insights for clinical stakeholders
- Maintains confidentiality when handling sensitive physician performance data
- Facilitates communication between clinical and administrative teams""",
        "requirements": """Experience / Skill Requirements:
- Minimum of three years of experience in clinical/healthcare data analysis (radiology experience preferred)
- Experience with data visualization tools (e.g., Power BI)
- Proficiency in SQL and at least one statistical or programming language (e.g., Python, R, SAS)
- Experience working with EHR, RIS and/or PACS systems
- Experience supporting quality initiatives or clinical improvement projects
- Knowledge of healthcare quality metrics and improvement methodologies
- Ability to leverage AI assistants for report generation, data interpretation, and administrative tasks
- Ability to manage multiple projects and deadlines
- Advanced Excel skills (pivot tables, formulas, data modeling)
- Excellent communication skills with the ability to present data clearly

Education: Bachelor's degree in Health Informatics, Statistics, Data Science or a related field.
Work Schedule: Monday through Friday, on-site in San Antonio, TX. No relocation assistance.""",
    },
]


def job_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


async def main():
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    inserted_ids = []

    try:
        for job in JOBS:
            jid = job_id(job["url"])
            existing = await db.fetchone("SELECT id FROM jobs WHERE id = ?", (jid,))
            if existing:
                print(f"Already exists: {job['title']} ({jid})")
                inserted_ids.append(jid)
                continue

            await db.execute(
                """INSERT INTO jobs
                   (id, url, source, title, company, location, work_type,
                    salary_min, salary_max, description, requirements, posted_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    jid,
                    job["url"],
                    job["source"],
                    job["title"],
                    job["company"],
                    job["location"],
                    job["work_type"],
                    job["salary_min"],
                    job["salary_max"],
                    job["description"],
                    job["requirements"],
                    job["posted_date"],
                ),
            )
            await db.commit()
            print(f"Inserted: {job['title']} (id: {jid})")
            inserted_ids.append(jid)

        # Score all inserted jobs
        from src.services.scorer import ScorerService
        scorer = ScorerService()
        try:
            for jid in inserted_ids:
                row = await db.fetchone("SELECT * FROM jobs WHERE id = ?", (jid,))
                if not row:
                    continue
                job_dict = dict(row)
                print(f"\nScoring: {job_dict['title']}...")
                score_result = await scorer.score_job(job_dict)
                await db.execute(
                    "UPDATE jobs SET fit_score = ?, fit_rationale = ? WHERE id = ?",
                    (score_result.get("score"), json.dumps(score_result), jid),
                )
                await db.commit()
                fit = score_result.get("score", 0)
                print(f"  Score: {fit}/100")
                if score_result.get("dealbreaker_triggered"):
                    print("  WARNING: Dealbreaker triggered")
                rationale = score_result.get("rationale") or score_result.get("summary", "")
                if rationale:
                    print(f"  Rationale: {rationale[:200]}")
        finally:
            await scorer.close()

        print("\nDone. Job IDs:")
        for jid in inserted_ids:
            print(f"  {jid}")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
