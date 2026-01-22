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
| `backend/src/routes/search.py` | Batch search endpoint, runs scrapers |
| `backend/src/scrapers/base.py` | Abstract base class for scrapers |
| `backend/src/scrapers/heb.py` | H-E-B careers scraper |
| `backend/src/scrapers/indeed.py` | Indeed job board scraper |
| `backend/data/ai_employers.md` | Target employer list for San Antonio |
| `frontend/src/services/api.js` | Frontend API client |
| `frontend/src/pages/Dashboard.jsx` | Main dashboard with scraper controls |

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

**Phase 2 In Progress**: Scraping (as of 2026-01-22)

Completed:
- crawl4ai integration
- H-E-B scraper (`backend/src/scrapers/heb.py`) - working
- Indeed scraper (`backend/src/scrapers/indeed.py`) - working
- Wellfound scraper (`backend/src/scrapers/wellfound.py`) - implemented
- Batch search endpoint (`POST /api/search/run`) with multi-source support
- Dashboard dropdown to select sources (All Sources / H-E-B / Indeed / Wellfound)
- San Antonio AI employers list (`backend/data/ai_employers.md`) - 34 companies

Not started:
- LinkedIn scraper (deprioritized - aggressive anti-bot, requires auth)
- Company career page scrapers (generic)
- Deduplication logic (beyond URL-based job IDs)

**Phase 3 TODO**: Scoring & Ranking
- User profile setup (skills, preferences, deal-breakers)
- LLM-based job fit scoring
- Fit rationale generation
- Job ranking by score
- Vector embeddings for semantic search

**Phase 4 TODO**: Application Support
- Resume tailoring with LLM
- Cover letter generation
- Application tracking workflow
- Email/calendar integration (stretch)

**Phase 5 TODO**: Automation & Polish
- Scheduled scraping (cron or background tasks)
- Email/Slack notifications for new high-fit jobs
- Analytics dashboard (applications sent, response rates)
- Mobile-friendly UI improvements

## Scrapers

| Scraper | File | Status | Notes |
|---------|------|--------|-------|
| H-E-B | `scrapers/heb.py` | Working | Uses crawl4ai, extracts salary |
| Indeed | `scrapers/indeed.py` | Working | Pagination, salary parsing, may hit CAPTCHAs |
| Wellfound | `scrapers/wellfound.py` | Implemented | Startup jobs, extracts Apollo GraphQL state from Next.js |
| LinkedIn | `scrapers/linkedin.py` | Stub | Deprioritized - too aggressive anti-bot |
| Company | `scrapers/company.py` | Stub | Generic career page scraper |

### Running Scrapers

**Via Dashboard**: Select source from dropdown, click "Run"

**Via API**:
```bash
# All sources (default)
curl -X POST "http://localhost:8000/api/search/run"

# Indeed only with custom query
curl -X POST "http://localhost:8000/api/search/run?sources=indeed&keywords=machine+learning+engineer&max_pages=5"

# HEB only
curl -X POST "http://localhost:8000/api/search/run?sources=heb&keywords=data"
```

**Parameters**:
- `location` (default: "San Antonio, TX")
- `keywords` (default: "data scientist")
- `sources` (default: "heb,indeed") - comma-separated
- `max_pages` (default: 3) - Indeed pagination limit

## Target Employers

See `backend/data/ai_employers.md` for full list of 34 San Antonio AI/ML employers organized by:
- Local Anchors (USAA, H-E-B, Frost Bank, Rackspace, Valero, CPS Energy)
- Research & Academia (SwRI, UTSA, UT Health)
- Defense & Government (Jaxon, Booz Allen, Lockheed, Northrop, etc.)
- Startups (NeuScience, AI Cowboys, Quickpath, GaitIQ)
- Consulting (Deloitte, PwC, Accenture, TCS)

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
