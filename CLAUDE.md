# Canopy - Claude Code Context

## Project Purpose

Canopy is a personal job search assistant for finding data science, ML, and AI positions in San Antonio and Austin (including remote/hybrid). It aggregates job postings, tracks new listings, scores jobs by fit, and helps tailor resumes and cover letters.

## Architecture Overview

```
Frontend (React + Vite)  →  Backend API (Litestar)  →  SQLite + sqlite-vec
                                    ↓
                         Services (LLM, Scraping, Scoring)
```

### Key Layers

1. **Frontend** (`frontend/src/`): React SPA with Tailwind CSS
   - `pages/` - Dashboard, JobList, JobDetail, Settings
   - `services/api.js` - API client functions

2. **Backend** (`backend/src/`): Async Python API
   - `app.py` - Litestar application entry point
   - `routes/` - API endpoint controllers
   - `services/` - Business logic (LLM, scraping, parsing)
   - `scrapers/` - Job board scraper implementations

3. **Database**: SQLite with extensions
   - `sqlite-vec` for vector similarity search
   - `FTS5` for full-text search
   - Schema defined in `db.py`

## Key Files

| File | Purpose |
|------|---------|
| `backend/src/app.py` | Litestar app setup, lifespan, routes |
| `backend/src/config.py` | Environment settings via pydantic-settings |
| `backend/src/db.py` | Database connection, schema, helpers |
| `backend/src/models.py` | Pydantic request/response models |
| `backend/src/services/llm.py` | LLM provider abstraction (Perplexity/Claude) |
| `backend/src/routes/jobs.py` | Job CRUD and search endpoints |
| `frontend/src/services/api.js` | Frontend API client |

## Common Commands

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m src.app                    # Run dev server
ruff check src/ && ruff format src/  # Lint
pytest tests/ -v                     # Test

# Frontend
cd frontend
npm install
npm run dev      # Dev server at :5173
npm run build    # Production build
npm run lint     # ESLint
```

## Data Flow

1. **Job Discovery**: Scraper → Parse with LLM → Generate embedding → Store in DB
2. **Job Scoring**: Load job + user profile → LLM generates fit score + rationale
3. **Resume Tailoring**: Job description + master resume → LLM tailors → User reviews
4. **Cover Letter**: Job + profile + templates → LLM generates → User edits

## Database Tables

- `jobs` - Scraped job postings with metadata
- `jobs_fts` - FTS5 virtual table for full-text search
- `search_runs` - Batch search history
- `applications` - Job application tracking
- `company_sources` - Configured career page sources

## LLM Provider

Configured via `LLM_PROVIDER` env var:
- `perplexity` - Default, uses Perplexity API
- `claude` - Fallback, uses Anthropic API

Both implement `LLMProvider` interface with `complete()` and `complete_json()` methods.

## Current Phase

**Phase 1 Complete**: Foundation
- Project structure
- Database schema with FTS5
- Basic CRUD endpoints
- React frontend scaffold
- CI pipelines

**Next**: Phase 2 (Scraping)
- crawl4ai integration
- Indeed/LinkedIn scrapers
- Batch search with state tracking
- Deduplication logic

## Environment Variables

```
PERPLEXITY_API_KEY   - Perplexity API key
ANTHROPIC_API_KEY    - Claude API key (backup)
LLM_PROVIDER         - "perplexity" or "claude"
DATABASE_PATH        - SQLite file path
SCRAPE_DELAY_SECONDS - Rate limit for scrapers
LOG_LEVEL            - Logging verbosity
```

## Notes

- Profile data stored in `backend/data/profile.json`
- User's resume/docs go in `backend/profile/` (gitignored)
- Job IDs are SHA256 hashes of URLs (first 16 chars)
- All scrapers should respect 2+ second delays
