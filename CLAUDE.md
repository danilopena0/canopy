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
| `backend/src/services/scorer.py` | Job fit scoring service with LLM |
| `backend/src/services/embeddings.py` | Vector embeddings with sentence-transformers |
| `backend/src/services/resume.py` | Resume tailoring service with LLM |
| `backend/src/services/cover.py` | Cover letter generation service with LLM |
| `backend/src/routes/jobs.py` | Job CRUD, search, scoring, and embedding endpoints |
| `backend/src/routes/applications.py` | Application tracking, tailor/cover endpoints |
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

- `jobs` - Scraped job postings with metadata, fit scores, and embeddings
- `jobs_fts` - FTS5 virtual table for full-text search
- `search_runs` - Batch search history
- `applications` - Job application tracking
- `company_sources` - Configured career page sources

### Jobs Table Key Columns

| Column | Type | Purpose |
|--------|------|---------|
| `fit_score` | REAL | LLM-generated job fit score (0-100) |
| `fit_rationale` | TEXT | Explanation of the fit score |
| `embedding` | BLOB | Vector embedding for semantic search (384 dims) |
| `dedup_key` | TEXT | Normalized key for deduplication |
| `duplicate_of` | TEXT | Reference to canonical job if duplicate |

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

**Phase 3 Complete**: Scoring & Ranking (as of 2026-01-29)

Completed:
- User profile setup (`backend/data/profile.json`) with skills, preferences, deal-breakers
- LLM-based job fit scoring (`services/scorer.py`)
- Fit rationale generation with matching/missing skills
- Job filtering by minimum score (`GET /api/jobs/?min_score=50`)
- Vector embeddings for semantic search (`services/embeddings.py`)
- Semantic search endpoint (`GET /api/jobs/semantic-search?q=...`)
- Similar jobs endpoint (`GET /api/jobs/similar/{job_id}`)

**Phase 4 Complete**: Application Support (as of 2026-01-24)

Completed:
- Resume tailoring with LLM (`backend/src/services/resume.py`)
- Cover letter generation with tone options (`backend/src/services/cover.py`)
- Document storage in `backend/profile/` (gitignored)
- API endpoints: `POST /api/applications/{job_id}/tailor`, `POST /api/applications/{job_id}/cover`
- `GET /api/documents` endpoint to list available documents
- JobDetail UI with tailor/cover buttons, tone selector, copy-to-clipboard
- Generated content saved to applications table and displayed on reload

Not started:
- Application tracking workflow improvements
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

## Resume & Cover Letter Generation

### Document Storage Structure

```
backend/profile/           # Gitignored - user's documents
  resume.md                # Master resume (required for tailoring)
  experience/              # Additional experience documents (optional)
    project_1.md
    leadership_examples.md
  templates/               # Cover letter templates (optional)
    cover_letter_base.md
```

### API Endpoints

```bash
# List available documents
curl http://localhost:8000/api/documents

# Tailor resume for a job
curl -X POST "http://localhost:8000/api/applications/{job_id}/tailor"

# Generate cover letter with tone
curl -X POST "http://localhost:8000/api/applications/{job_id}/cover" \
  -H "Content-Type: application/json" \
  -d '{"tone": "professional"}'  # or "enthusiastic", "casual"
```

### Usage: Web UI

1. Create `backend/profile/resume.md` with your master resume in markdown
2. Optionally add experience documents in `backend/profile/experience/`
3. Go to a job detail page in the UI
4. Click "Tailor Resume" to generate a tailored version
5. Select tone and click "Generate Cover Letter"
6. Use "Copy to Clipboard" to copy generated content

Generated content is saved to the database and will reload when you revisit the job.

### Usage: Claude Code (Direct)

You can also ask Claude Code directly to tailor your resume or write cover letters. This doesn't require API keys.

**Helper script to get job details:**
```bash
cd backend
python scripts/get_job.py --list        # List recent jobs with IDs
python scripts/get_job.py <job_id>      # Get full job details
```

**Example prompts to Claude Code:**
- "Read my resume at backend/profile/resume.md and tailor it for job ID abc12345"
- "Write a cover letter for the Data Scientist position at USAA based on my resume"
- "Look at job abc12345 and tell me how well my resume matches"

Claude Code will read your files and generate content directly in the conversation.

## Job Scoring

LLM-based scoring evaluates how well each job matches your profile using a 100-point rubric:
- Title match (25 pts)
- Skills overlap (35 pts)
- Location/work type (15 pts)
- Salary fit (10 pts)
- Experience level (10 pts)
- Industry preference (5 pts bonus)

If a dealbreaker is triggered, the score is automatically set to 0.

### Profile Setup

Create `backend/data/profile.json` with your preferences:

```json
{
  "name": "Your Name",
  "target_titles": ["Data Scientist", "ML Engineer", "AI Engineer"],
  "skills": {
    "languages": ["Python", "SQL", "R"],
    "ml_tools": ["TensorFlow", "PyTorch", "scikit-learn"],
    "platforms": ["AWS", "GCP", "Databricks"],
    "other": ["NLP", "Computer Vision", "MLOps"]
  },
  "experience_years": 5,
  "locations": ["San Antonio, TX", "Austin, TX", "Remote"],
  "work_types": ["remote", "hybrid"],
  "industries": ["Tech", "Finance", "Healthcare"],
  "min_salary": 120000,
  "dealbreakers": ["clearance required", "on-call 24/7"]
}
```

### Scoring API

```bash
# Score a single job
curl -X POST "http://localhost:8000/api/jobs/{job_id}/score"

# Score multiple jobs
curl -X POST "http://localhost:8000/api/jobs/score-batch" \
  -H "Content-Type: application/json" \
  -d '{"job_ids": ["abc123", "def456"]}'

# List jobs with minimum score
curl "http://localhost:8000/api/jobs/?min_score=70"
```

### Auto-Scoring

New jobs are **automatically scored** when scraped (enabled by default). To disable:
```bash
curl -X POST "http://localhost:8000/api/search/run?auto_score=false"
```

### Bulk Scoring Script

Score all existing unscored jobs:
```bash
cd backend
source venv/bin/activate
python scripts/score_jobs.py           # Score unscored jobs only
python scripts/score_jobs.py --all     # Re-score all jobs
python scripts/score_jobs.py --limit 5 # Score only 5 jobs
```

## Vector Embeddings & Semantic Search

Jobs are embedded using the `all-MiniLM-L6-v2` model (384 dimensions) for semantic similarity search. The model is ~90MB and downloaded on first use.

### Embedding API

```bash
# Embed a single job
curl -X POST "http://localhost:8000/api/jobs/{job_id}/embed"

# Embed all jobs without embeddings (backfill)
curl -X POST "http://localhost:8000/api/jobs/embed-all"

# Find similar jobs
curl "http://localhost:8000/api/jobs/similar/{job_id}?limit=10"

# Semantic search (search by meaning, not keywords)
curl "http://localhost:8000/api/jobs/semantic-search?q=machine+learning+NLP&limit=20"
```

### Semantic vs Full-Text Search

| Feature | Full-Text (`/search`) | Semantic (`/semantic-search`) |
|---------|----------------------|------------------------------|
| Query | Keywords must match | Meaning-based matching |
| Example | "python developer" | "coding in snake language" |
| Speed | Fast (FTS5 index) | Slower (computes similarity) |
| Setup | Automatic | Requires `embed-all` first |

## Notes

- Profile data stored in `backend/data/profile.json`
- User's resume/docs go in `backend/profile/` (gitignored)
- Job IDs are SHA256 hashes of URLs (first 16 chars)
- All scrapers should respect 2+ second delays
- First embedding call downloads ~90MB model (cached in `~/.cache/torch/`)
- Scoring requires LLM API key; embeddings are fully local (no API needed)
