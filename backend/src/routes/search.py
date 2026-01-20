"""Search routes for batch job searches and source management."""

import json
from typing import Annotated

from litestar import Controller, get, post
from litestar.di import Provide
from litestar.params import Parameter

from ..db import Database, db_dependency
from ..models import (
    CompanySource,
    CompanySourceCreate,
    MessageResponse,
    SearchRun,
)


class SearchController(Controller):
    """Controller for search-related endpoints."""

    path = "/api/search"
    dependencies = {"db": Provide(db_dependency)}

    @post("/run")
    async def run_search(self, db: Database) -> MessageResponse:
        """Trigger a batch search across all enabled sources.

        TODO: Implement in Phase 2 with actual scraping logic.
        """
        return MessageResponse(
            message="Search functionality will be implemented in Phase 2"
        )

    @get("/runs")
    async def list_search_runs(
        self,
        db: Database,
        limit: Annotated[int, Parameter(query="limit", ge=1, le=100)] = 20,
    ) -> list[SearchRun]:
        """List past search runs."""
        rows = await db.fetchall(
            "SELECT * FROM search_runs ORDER BY run_at DESC LIMIT ?",
            (limit,),
        )
        return [SearchRun(**dict(row)) for row in rows]

    @get("/sources")
    async def list_sources(self, db: Database) -> list[CompanySource]:
        """List configured job sources."""
        rows = await db.fetchall(
            "SELECT * FROM company_sources ORDER BY company_name"
        )
        return [CompanySource(**dict(row)) for row in rows]

    @post("/sources")
    async def add_source(
        self, db: Database, data: CompanySourceCreate
    ) -> CompanySource:
        """Add a new job source."""
        cursor = await db.execute(
            """
            INSERT INTO company_sources (company_name, careers_url, scrape_config, category)
            VALUES (?, ?, ?, ?)
            """,
            (
                data.company_name,
                data.careers_url,
                data.scrape_config,
                data.category,
            ),
        )
        await db.commit()

        row = await db.fetchone(
            "SELECT * FROM company_sources WHERE id = ?",
            (cursor.lastrowid,),
        )
        return CompanySource(**dict(row))
