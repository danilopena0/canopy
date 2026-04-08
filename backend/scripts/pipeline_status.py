#!/usr/bin/env python3
"""Show the full job application pipeline status.

Usage:
    python scripts/pipeline_status.py           # Full pipeline view
    python scripts/pipeline_status.py --stale   # Only show applications needing follow-up (>7 days)
    python scripts/pipeline_status.py --stage applied  # Filter by stage
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import Database
from src.config import get_settings

STAGES = {
    "shortlisted": "Shortlisted (not yet applied)",
    "applying":    "In Progress (drafting application)",
    "applied":     "Applied (awaiting response)",
    "interviewing": "Interviewing",
    "offer":       "Offer Received",
    "rejected":    "Rejected / Closed",
    "archived":    "Archived / Pass",
}


async def pipeline_status(stage_filter: str | None = None, stale_only: bool = False) -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    # Jobs with applications
    rows = await db.fetchall(
        """
        SELECT
            j.id, j.title, j.company, j.location, j.work_type,
            j.fit_score, j.status as job_status, j.url,
            a.id as app_id, a.applied_at, a.response,
            a.tailored_resume IS NOT NULL as has_resume,
            a.cover_letter IS NOT NULL as has_cover,
            julianday('now') - julianday(a.applied_at) as days_since_applied
        FROM jobs j
        LEFT JOIN applications a ON j.id = a.job_id
        WHERE j.status IN ('shortlisted', 'applying', 'applied', 'interviewing', 'offer')
           OR a.id IS NOT NULL
        ORDER BY j.fit_score DESC
        """
    )

    # Also show shortlisted jobs without applications
    shortlisted = await db.fetchall(
        """
        SELECT j.id, j.title, j.company, j.fit_score, j.url, j.work_type
        FROM jobs j
        LEFT JOIN applications a ON j.id = a.job_id
        WHERE j.status = 'shortlisted' AND a.id IS NULL
        ORDER BY j.fit_score DESC
        """
    )

    await db.disconnect()

    now = datetime.now(timezone.utc)

    print("=" * 80)
    print("JOB APPLICATION PIPELINE")
    print("=" * 80)

    # --- Shortlisted (no application yet) ---
    if shortlisted and (not stage_filter or stage_filter == "shortlisted"):
        print(f"\n## SHORTLISTED — ready to apply ({len(shortlisted)})\n")
        for r in shortlisted:
            r = dict(r)
            score = f"{r['fit_score']:.0f}/100" if r["fit_score"] else "?"
            wtype = (r.get("work_type") or "?")[:8]
            print(f"  [{score}] {r['title']} @ {r['company']} ({wtype})")
            print(f"    ID: {r['id']}  →  /apply {r['id']}")
        print()

    # --- Applications ---
    applied_rows = [dict(r) for r in rows if r["app_id"]]

    if stale_only:
        applied_rows = [r for r in applied_rows if r.get("days_since_applied") and r["days_since_applied"] > 7]

    # Group by response/status
    buckets: dict[str, list] = {
        "in_progress": [],
        "applied": [],
        "interviewing": [],
        "offer": [],
        "rejected": [],
    }

    for r in applied_rows:
        resp = (r.get("response") or "").lower()
        if resp in ("offer",):
            buckets["offer"].append(r)
        elif resp in ("interviewing", "phone_screen", "technical"):
            buckets["interviewing"].append(r)
        elif resp in ("rejected", "closed", "declined"):
            buckets["rejected"].append(r)
        elif r.get("applied_at"):
            buckets["applied"].append(r)
        else:
            buckets["in_progress"].append(r)

    labels = {
        "in_progress":  "IN PROGRESS — application being built",
        "applied":      "APPLIED — awaiting response",
        "interviewing": "INTERVIEWING",
        "offer":        "OFFER",
        "rejected":     "CLOSED / REJECTED",
    }

    for key, label in labels.items():
        items = buckets[key]
        if not items:
            continue
        if stage_filter and stage_filter != key:
            continue

        print(f"\n## {label} ({len(items)})\n")
        for r in items:
            score = f"{r['fit_score']:.0f}/100" if r["fit_score"] else "?"
            docs = []
            if r.get("has_resume"):
                docs.append("resume")
            if r.get("has_cover"):
                docs.append("cover")
            doc_str = f"[{', '.join(docs)}]" if docs else "[no docs]"

            days = r.get("days_since_applied")
            days_str = f" | {int(days)}d ago" if days else ""
            stale_flag = " ⚠ FOLLOW UP" if days and days > 7 else ""

            print(f"  [{score}] {r['title']} @ {r['company']}{days_str}{stale_flag}")
            print(f"    ID: {r['id']}  |  {doc_str}  |  Applied: {r.get('applied_at') or 'not recorded'}")

    print()

    # Summary counts
    total_applied = len(buckets["applied"]) + len(buckets["interviewing"]) + len(buckets["offer"])
    stale_count = sum(1 for r in buckets["applied"] if r.get("days_since_applied") and r["days_since_applied"] > 7)
    print(f"Summary: {len(shortlisted)} shortlisted | {total_applied} active | {stale_count} need follow-up")


def main():
    parser = argparse.ArgumentParser(description="Show job application pipeline")
    parser.add_argument("--stale", action="store_true", help="Only show applications needing follow-up (>7 days)")
    parser.add_argument("--stage", help="Filter by stage: shortlisted, applied, interviewing, offer, rejected")
    args = parser.parse_args()

    asyncio.run(pipeline_status(stage_filter=args.stage, stale_only=args.stale))


if __name__ == "__main__":
    main()
