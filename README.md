# Canopy

An intelligent job search and application assistant for data science, ML, and AI positions.

## Overview

Canopy is a fully agentic job search assistant. It automates the entire workflow — discovery, triage, networking, applying, and follow-up — through Claude Code slash commands that orchestrate specialized AI agents in parallel.

**Workflow:**
```
/hunt       → scrape + rank new jobs
/triage     → shortlist or pass each one
/network    → find contacts, draft outreach before applying
/apply      → parallel agents: resume + cover letter + project highlights
/pipeline   → see where everything stands
/follow-up  → draft nudges for anything stale
```

## Video Usage
https://github.com/user-attachments/assets/98ef6f3f-783d-44e2-8bc4-7f432a285188


## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Litestar (Python async framework) |
| Frontend | React + Vite + Tailwind CSS |
| Database | SQLite + sqlite-vec (vector search) + FTS5 |
| Scraping | crawl4ai + Playwright |
| LLM | Groq / Perplexity / Claude API |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- npm

### Running the Application

You need to run both the backend and frontend in separate terminals.

**Terminal 1 - Backend:**

```bash
cd backend

# Create virtual environment (first time only)
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS/WSL
# or: venv\Scripts\activate  # Windows PowerShell

# Install dependencies (first time only)
pip install -r requirements.txt

# Install Playwright browsers for web scraping (first time only)
playwright install

# Copy environment file and add your API keys (first time only)
cp ../.env.example .env

# Run the server
python -m src.app
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/schema` for OpenAPI docs.

**Terminal 2 - Frontend:**

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

> **Note:** Run frontend commands from the `frontend/` directory, not the project root.

## Project Structure

```
canopy/
├── backend/
│   ├── src/
│   │   ├── app.py          # Litestar application
│   │   ├── config.py       # Settings (pydantic-settings)
│   │   ├── db.py           # Database connection & schema
│   │   ├── models.py       # Pydantic models
│   │   ├── routes/         # API route handlers
│   │   ├── services/       # Business logic (LLM, scoring, embeddings, resume, cover letter)
│   │   ├── scrapers/       # Job board scrapers
│   │   └── utils/          # Utilities (deduplication)
│   ├── tests/
│   ├── scripts/            # CLI utilities (scoring, job lookup)
│   ├── data/               # Database, profile config, employer lists
│   └── profile/            # User resume & documents (gitignored)
├── frontend/
│   ├── src/
│   │   ├── pages/          # Dashboard, JobList, JobDetail, Settings
│   │   ├── components/     # Reusable UI components
│   │   ├── services/       # API client
│   │   └── hooks/          # Custom React hooks
│   └── public/
└── .github/workflows/      # CI pipelines
```

## Claude Code Skills

All job search workflows run through slash commands in Claude Code. Each command orchestrates one or more specialized agents.

| Command | Args | What it does |
|---------|------|-------------|
| `/hunt` | `[--sources] [--keywords] [--min-score]` | Run scrapers, return ranked shortlist |
| `/triage` | — | Review new high-fit jobs, mark shortlisted or pass |
| `/network` | `<job_id or company>` | Find contacts, draft LinkedIn outreach |
| `/ingest-job` | `<url>` | Scrape a specific URL, parse, store, score |
| `/apply` | `<job_id or url>` | Tailored resume + cover letter + project highlights (parallel) |
| `/interview-prep` | `<job_id>` | Full prep with Mermaid diagrams |
| `/job-help` | `<url>` | End-to-end: ingest → apply → interview prep |
| `/pipeline` | `[--stale]` | Application pipeline status + next actions |
| `/follow-up` | `[job_id]` | Draft follow-ups for stale applications and networking |

### Finding a Job ID

```bash
cd backend && source venv/bin/activate
python scripts/get_job.py --list        # shows full 16-char IDs
python scripts/get_job.py <job_id>      # full job details
```

Or run `/hunt` — job IDs are printed next to each result.

### Weekly Rhythm

```
Monday:   /hunt              → new jobs scraped and ranked
          /triage            → shortlist the best ones

Tuesday:  /network <job_id>  → find contacts, send outreach before applying
          /apply <job_id>    → full application package

Friday:   /pipeline          → see where everything stands
          /follow-up         → draft nudges for anything stale
```

## API Endpoints

### Jobs
- `GET /api/jobs` - List jobs with filters (status, source, company, min_score, work_type)
- `GET /api/jobs/{job_id}` - Get job details
- `POST /api/jobs` - Create a job
- `PATCH /api/jobs/{job_id}` - Update job status/notes
- `DELETE /api/jobs/{job_id}` - Delete a job
- `GET /api/jobs/search` - Full-text search

### Scoring
- `POST /api/jobs/{job_id}/score` - Score a single job
- `POST /api/jobs/score-batch` - Score multiple jobs

### Embeddings & Semantic Search
- `POST /api/jobs/{job_id}/embed` - Generate embedding for a job
- `POST /api/jobs/embed-all` - Embed all jobs without embeddings
- `GET /api/jobs/similar/{job_id}` - Find similar jobs by vector similarity
- `GET /api/jobs/semantic-search` - Search jobs by meaning

### Search
- `POST /api/search/run` - Trigger batch search (params: location, keywords, sources, max_pages, auto_score)
- `GET /api/search/runs` - List past searches
- `GET /api/search/sources` - List configured sources
- `POST /api/search/sources` - Add new source
- `POST /api/search/backfill-dedup` - Backfill deduplication keys
- `GET /api/search/duplicates` - Find duplicate jobs

### Applications
- `GET /api/applications` - List applications
- `GET /api/applications/{application_id}` - Get application details
- `POST /api/applications` - Create an application
- `PATCH /api/applications/{application_id}` - Update an application
- `POST /api/applications/{job_id}/tailor` - Generate tailored resume
- `POST /api/applications/{job_id}/cover` - Generate cover letter

### Documents
- `GET /api/documents` - List available profile documents

### Profile
- `GET /api/profile` - Get user profile
- `PUT /api/profile` - Update profile

### Health
- `GET /api/health` - Health check

## Configuration

Create a `.env` file in the backend directory (or copy from `.env.example`):

```bash
GROQ_API_KEY=your_key_here
PERPLEXITY_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
LLM_PROVIDER=groq
DATABASE_PATH=./data/canopy.db
SCRAPE_DELAY_SECONDS=2
LOG_LEVEL=INFO
```

## Scrapers

| Scraper | Status | Notes |
|---------|--------|-------|
| Indeed | Working | Pagination support, salary parsing |
| H-E-B | Working | Extracts salary info |
| Wellfound | Working | Startup jobs via Apollo GraphQL |
| LinkedIn | Stub | Deprioritized due to anti-bot measures |
| Company | Stub | Generic career page scraper |

New jobs are automatically scored when scraped (disable with `auto_score=false`).

## Development

### Running Tests

```bash
# Backend
cd backend
pytest tests/ -v

# Frontend
cd frontend
npm run lint
```

### Code Quality

```bash
# Backend linting
cd backend
ruff check src/
ruff format src/

# Frontend linting
cd frontend
npm run lint
```

### Utility Scripts

```bash
cd backend
source venv/bin/activate

# Find job IDs
python scripts/get_job.py --list            # List recent jobs (full IDs shown)
python scripts/get_job.py <job_id>          # Full details for one job

# Hunt and score
python scripts/hunt_jobs.py                 # Run scrapers + show top matches
python scripts/hunt_jobs.py --no-scrape     # Query existing DB only
python scripts/score_jobs.py                # Score unscored jobs only
python scripts/score_jobs.py --all          # Re-score all

# Pipeline
python scripts/pipeline_status.py          # Full pipeline view
python scripts/pipeline_status.py --stale  # Only items needing follow-up

# Networking
python scripts/list_contacts.py                        # All contacts
python scripts/list_contacts.py --company USAA         # Filter by company
python scripts/add_contact.py "Jane Smith" "USAA" \
  --role "Sr Data Scientist" \
  --linkedin "https://linkedin.com/in/..." \
  --met-via "LinkedIn search"
```

## License

MIT
