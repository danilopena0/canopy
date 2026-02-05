# Canopy

An intelligent job search and application assistant for data science, ML, and AI positions.

## Overview

Canopy helps you:
- Aggregate job postings from multiple sources (Indeed, H-E-B, Wellfound)
- Track new listings across searches with cross-source deduplication
- Score and rank jobs by fit against your profile using LLM-based evaluation
- Search jobs semantically using vector embeddings
- Tailor resumes to specific job descriptions
- Generate customized cover letters with tone selection

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Litestar (Python async framework) |
| Frontend | React + Vite + Tailwind CSS |
| Database | SQLite + sqlite-vec (vector search) + FTS5 |
| Scraping | crawl4ai + Playwright |
| LLM | Perplexity API / Claude API |
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
PERPLEXITY_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
LLM_PROVIDER=perplexity
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

# List recent jobs / get job details
python scripts/get_job.py --list
python scripts/get_job.py <job_id>

# Score jobs
python scripts/score_jobs.py           # Unscored jobs only
python scripts/score_jobs.py --all     # Re-score all
python scripts/score_jobs.py --limit 5 # Score a batch
```

## License

MIT
