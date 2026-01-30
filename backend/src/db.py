"""Database connection and schema management."""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import aiosqlite

from .config import get_settings

logger = logging.getLogger(__name__)

# SQL Schema definitions
SCHEMA_SQL = """
-- Jobs table: stores all scraped job postings
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    work_type TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    description TEXT,
    requirements TEXT,
    posted_date DATE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fit_score REAL,
    fit_rationale TEXT,
    status TEXT DEFAULT 'new',
    notes TEXT,
    dedup_key TEXT,
    duplicate_of TEXT REFERENCES jobs(id)
);

-- Search runs table: tracks batch search history
CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sources TEXT,
    jobs_found INTEGER,
    new_jobs INTEGER,
    duration_seconds REAL
);

-- Applications table: tracks job applications
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT REFERENCES jobs(id),
    resume_version TEXT,
    cover_letter TEXT,
    tailored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP,
    response TEXT
);

-- Company sources table: configured job board sources
CREATE TABLE IF NOT EXISTS company_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    careers_url TEXT NOT NULL,
    scrape_config TEXT,
    category TEXT,
    enabled BOOLEAN DEFAULT TRUE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON jobs(scraped_at);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
"""

# Indexes that depend on migrated columns (run after migrations)
DEDUP_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_jobs_dedup_key ON jobs(dedup_key);
CREATE INDEX IF NOT EXISTS idx_jobs_duplicate_of ON jobs(duplicate_of);
"""

# Full-text search virtual table
FTS_SQL = """
-- Full-text search on job listings
CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
    title,
    company,
    description,
    requirements,
    content='jobs',
    content_rowid='rowid'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
    INSERT INTO jobs_fts(rowid, title, company, description, requirements)
    VALUES (NEW.rowid, NEW.title, NEW.company, NEW.description, NEW.requirements);
END;

CREATE TRIGGER IF NOT EXISTS jobs_ad AFTER DELETE ON jobs BEGIN
    INSERT INTO jobs_fts(jobs_fts, rowid, title, company, description, requirements)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.company, OLD.description, OLD.requirements);
END;

CREATE TRIGGER IF NOT EXISTS jobs_au AFTER UPDATE ON jobs BEGIN
    INSERT INTO jobs_fts(jobs_fts, rowid, title, company, description, requirements)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.company, OLD.description, OLD.requirements);
    INSERT INTO jobs_fts(rowid, title, company, description, requirements)
    VALUES (NEW.rowid, NEW.title, NEW.company, NEW.description, NEW.requirements);
END;
"""


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Establish database connection and initialize schema."""
        # Ensure the data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        # Enable foreign keys
        await self._connection.execute("PRAGMA foreign_keys = ON")

        # Initialize schema
        await self._init_schema()

        logger.info(f"Connected to database: {self.db_path}")

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        # Create main tables
        await self._connection.executescript(SCHEMA_SQL)

        # Create FTS virtual table and triggers
        await self._connection.executescript(FTS_SQL)

        # Run migrations for existing databases
        await self._run_migrations()

        # Create indexes that depend on migrated columns
        await self._connection.executescript(DEDUP_INDEXES_SQL)

        await self._connection.commit()
        logger.info("Database schema initialized")

    async def _run_migrations(self) -> None:
        """Run migrations for existing databases."""
        if self._connection is None:
            return

        # Check if dedup_key column exists in jobs table
        cursor = await self._connection.execute("PRAGMA table_info(jobs)")
        job_columns = {row[1] for row in await cursor.fetchall()}

        if "dedup_key" not in job_columns:
            logger.info("Migrating: adding dedup_key column")
            await self._connection.execute(
                "ALTER TABLE jobs ADD COLUMN dedup_key TEXT"
            )

        if "duplicate_of" not in job_columns:
            logger.info("Migrating: adding duplicate_of column")
            await self._connection.execute(
                "ALTER TABLE jobs ADD COLUMN duplicate_of TEXT REFERENCES jobs(id)"
            )

        # Check for new application columns (Phase 4: resume/cover letter)
        cursor = await self._connection.execute("PRAGMA table_info(applications)")
        app_columns = {row[1] for row in await cursor.fetchall()}

        if "tailored_resume" not in app_columns:
            logger.info("Migrating: adding tailored_resume column to applications")
            await self._connection.execute(
                "ALTER TABLE applications ADD COLUMN tailored_resume TEXT"
            )

        if "resume_highlights" not in app_columns:
            logger.info("Migrating: adding resume_highlights column to applications")
            await self._connection.execute(
                "ALTER TABLE applications ADD COLUMN resume_highlights TEXT"
            )

        if "cover_tone" not in app_columns:
            logger.info("Migrating: adding cover_tone column to applications")
            await self._connection.execute(
                "ALTER TABLE applications ADD COLUMN cover_tone TEXT"
            )

        # Check for embedding column (Phase 3: vector embeddings)
        if "embedding" not in job_columns:
            logger.info("Migrating: adding embedding column to jobs")
            await self._connection.execute(
                "ALTER TABLE jobs ADD COLUMN embedding BLOB"
            )

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the active database connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        return self._connection

    async def execute(
        self, sql: str, parameters: tuple | dict | None = None
    ) -> aiosqlite.Cursor:
        """Execute a SQL statement."""
        if parameters:
            return await self.connection.execute(sql, parameters)
        return await self.connection.execute(sql)

    async def executemany(
        self, sql: str, parameters: list[tuple | dict]
    ) -> aiosqlite.Cursor:
        """Execute a SQL statement with multiple parameter sets."""
        return await self.connection.executemany(sql, parameters)

    async def fetchone(
        self, sql: str, parameters: tuple | dict | None = None
    ) -> aiosqlite.Row | None:
        """Execute a query and fetch one result."""
        cursor = await self.execute(sql, parameters)
        return await cursor.fetchone()

    async def fetchall(
        self, sql: str, parameters: tuple | dict | None = None
    ) -> list[aiosqlite.Row]:
        """Execute a query and fetch all results."""
        cursor = await self.execute(sql, parameters)
        return await cursor.fetchall()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.connection.commit()


# Global database instance
_db: Database | None = None


async def get_database() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        settings = get_settings()
        _db = Database(settings.database_path)
        await _db.connect()
    return _db


async def close_database() -> None:
    """Close the global database instance."""
    global _db
    if _db is not None:
        await _db.disconnect()
        _db = None


async def db_dependency() -> AsyncGenerator[Database, None]:
    """Dependency injection for database access in routes."""
    db = await get_database()
    yield db
