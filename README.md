# Canopy

An intelligent job search and application assistant for data science, ML, and AI positions.

## Overview

Canopy helps you:
- Aggregate job postings from multiple sources
- Track new listings across searches (see only what's new)
- Score and rank jobs by fit against your profile
- Tailor resumes to specific job descriptions
- Generate customized cover letters

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Litestar (Python async framework) |
| Frontend | React + Vite + Tailwind CSS |
| Database | SQLite + sqlite-vec (vector search) + FTS5 |
| Scraping | crawl4ai |
| LLM | Perplexity API / Claude API |

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
│   │   ├── services/       # Business logic
│   │   └── scrapers/       # Job board scrapers
│   ├── tests/
│   ├── scripts/
│   └── data/               # SQLite database (gitignored)
├── frontend/
│   ├── src/
│   │   ├── pages/          # React page components
│   │   ├── components/     # Reusable UI components
│   │   ├── services/       # API client
│   │   └── hooks/          # Custom React hooks
│   └── public/
└── .github/workflows/      # CI pipelines
```

## API Endpoints

### Jobs
- `GET /api/jobs` - List jobs with filters
- `GET /api/jobs/{id}` - Get job details
- `PATCH /api/jobs/{id}` - Update job status/notes
- `GET /api/jobs/search?q=` - Full-text search

### Search
- `POST /api/search/run` - Trigger batch search
- `GET /api/search/runs` - List past searches
- `GET /api/search/sources` - List configured sources
- `POST /api/search/sources` - Add new source

### Applications
- `POST /api/applications/{job_id}/tailor` - Generate tailored resume
- `POST /api/applications/{job_id}/cover` - Generate cover letter
- `GET /api/applications` - List applications

### Profile
- `GET /api/profile` - Get user profile
- `PUT /api/profile` - Update profile

## Configuration

Create a `.env` file in the backend directory:

```bash
PERPLEXITY_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
LLM_PROVIDER=perplexity
DATABASE_PATH=./data/canopy.db
SCRAPE_DELAY_SECONDS=2
LOG_LEVEL=INFO
```

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

## Implementation Status

- [x] Phase 1: Foundation (project setup, DB schema, basic CRUD)
- [ ] Phase 2: Scraping (crawl4ai integration, job board scrapers)
- [ ] Phase 3: Intelligence (LLM parsing, embeddings, scoring)
- [ ] Phase 4: Application Tools (resume tailoring, cover letters)
- [ ] Phase 5: Polish (full UI, deployment)

## License

MIT
