# Canopy — Architecture

## 1. One-Liner

A fully agentic job search assistant that automates the entire application workflow — scraping, scoring, networking, resume tailoring, and cover letter generation — through Claude Code slash commands that orchestrate specialized AI agents in parallel.

## 2. The Problem

Job searching for ML/AI roles is high-volume, low-signal work: hundreds of postings across multiple boards, most of which are poor fits. Then for the few good matches, the application process requires tailoring resumes and writing cover letters — tedious work that takes hours per application. Canopy solves both halves: automated scraping + LLM scoring surfaces the 5% of roles worth applying to, and parallel Claude agents generate a complete application package (tailored resume + cover letter + project highlights) in minutes.

## 3. System Diagram

```mermaid
flowchart TD
    subgraph ClaudeCode["Claude Code (AI Layer)"]
        HUNT[/hunt — Scrape + Rank]
        TRIAGE[/triage — Shortlist or Pass]
        APPLY[/apply — Full Application Package]
        NETWORK[/network — Find Contacts]
        PIPELINE[/pipeline — Status View]
    end

    subgraph Agents["Specialized Agents"]
        INGESTOR[job-ingestor\nScrape → Parse → Score]
        TAILOR[resume-tailor\nOpus]
        COVER[cover-writer\nOpus]
        MATCHER[project-matcher\nOpus]
        COACH[interview-coach\nOpus]
    end

    subgraph Backend["Litestar API\nbackend/src/"]
        APP[app.py\nAsync Entry Point]
        ROUTES[routes/\njobs, applications, search]
        SERVICES[services/\nllm, scorer, embeddings\nresume, cover, parser]
        SCRAPERS[scrapers/\nindeed, heb, wellfound]
    end

    subgraph Storage["Storage Layer"]
        SQLITE[(SQLite\ncanopy.db)]
        FTS5[FTS5 Virtual Table\nFull-Text Search]
        VEC[sqlite-vec\nVector Similarity]
        SQLITE --- FTS5 & VEC
    end

    subgraph Frontend["React + Vite\nfrontend/src/"]
        DASH[Dashboard]
        JOBLIST[JobList]
        JOBDET[JobDetail\nTailor / Cover buttons]
    end

    ClaudeCode --> Agents
    Agents --> Backend
    Frontend --> Backend
    Backend --> Storage
    SCRAPERS -- crawl4ai/Playwright --> SCRAPERS
```

## 4. Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Language | Python 3.11+ (backend), TypeScript (frontend) | Type-safe on both ends |
| API framework | Litestar | Async Python; auto-generated OpenAPI; better DI than FastAPI |
| Frontend | React + Vite + Tailwind CSS | Fast dev server; component-based UI; utility-first CSS |
| Database | SQLite + sqlite-vec + FTS5 | Zero-setup embedded DB; FTS5 for keyword search; sqlite-vec for vector similarity |
| Scraping | crawl4ai + Playwright | JavaScript-rendering support; structured extraction via LLM |
| LLM | Groq (default) / Perplexity / Claude | Groq free tier for speed; Claude for high-quality application docs |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Local 384-dim embeddings; zero cost; ~90MB model |
| Agent layer | Claude Code slash commands | Orchestrates specialized subagents for job search workflows |
| CI/CD | GitHub Actions | Automated testing on push |

## 5. Architectural Patterns

### Orchestrator-Worker Pattern (Agent Layer)
**Location:** `.claude/commands/` + `.claude/agents/`

Each Claude Code slash command (`/hunt`, `/apply`, `/triage`) is an orchestrator that dispatches to specialized subagents in parallel. `/apply` runs `resume-tailor`, `cover-writer`, and `project-matcher` simultaneously — three Opus agents producing documents concurrently. The orchestrator collects outputs and stores them to `backend/profile/applications/{job_id}/`.

**Why right here:** Resume tailoring, cover letter writing, and project matching are independent tasks with no data dependencies. Parallel execution cuts wall-clock time from 3× sequential to 1× parallel.

**Alternative considered:** Sequential agent calls within `/apply`. Rejected — no dependency between resume and cover letter; parallel is free speedup.

---

### Strategy Pattern (LLM Provider + Scrapers)
**Location:** `backend/src/services/llm.py` + `backend/src/scrapers/base.py`

`LLMProvider` is an abstract base with `complete()` and `complete_json()` methods. Groq, Perplexity, and Claude all implement this interface. Similarly, all scrapers inherit from `BaseScraper` with a `scrape(query, location, max_pages)` → `list[RawJob]` interface. New job boards are addable without modifying the batch search endpoint.

**Why right here:** Both LLMs and job boards are external services that change independently. The abstract interface insulates business logic from provider churn.

**Alternative considered:** Switch statements on provider name in route handlers. Rejected — adds provider logic to HTTP-layer code.

---

### Repository Pattern (Job Storage)
**Location:** `backend/src/db.py` + `backend/src/routes/jobs.py`

All database operations go through `db.py` helper functions. Route handlers never write raw SQL — they call `get_job(id)`, `create_job(data)`, `update_job(id, data)`. FTS5 and sqlite-vec are treated as storage extensions, not separate systems.

**Why right here:** SQLite with two virtual table extensions (FTS5 + sqlite-vec) is unusual. Centralizing all DB access in `db.py` means the extension-specific query syntax (FTS `MATCH`, vec `distance`) is in one place.

---

### Service Layer
**Location:** `backend/src/services/`

Six discrete services (`llm.py`, `scorer.py`, `embeddings.py`, `resume.py`, `cover.py`, `parser.py`) each have a single responsibility. Route handlers compose services but don't implement business logic themselves. `scorer.py` contains the 100-point scoring rubric; `embeddings.py` manages the sentence-transformer lifecycle; `resume.py` reads master resume and calls the LLM.

**Why right here:** Job scoring, resume tailoring, and embedding generation all involve complex domain logic that would overwhelm route handlers. The service layer keeps routes thin.

---

### Deduplication via Normalized Key
**Location:** `backend/src/utils/dedup.py`

Jobs are deduplicated via a `dedup_key` computed from normalized title + company + location. When a job is scraped, the dedup key is checked against existing jobs; if matched, `duplicate_of` is set rather than creating a duplicate record. This handles the same job appearing on Indeed and a company's direct site.

**Why right here:** Without deduplication, the same ML Scientist role at USAA appears 5 times from different sources. The normalized key handles title variations ("ML Engineer" vs "Machine Learning Engineer").

---

## 6. Data Flow

**Scenario: `/apply abc12345` (generate full application package)**

1. User types `/apply abc12345` in Claude Code — the slash command in `.claude/commands/apply.md` is invoked
2. Orchestrator reads job details via `python scripts/get_job.py abc12345` from `backend/`
3. Orchestrator spawns three Opus agents **in parallel**:
   - `resume-tailor` agent: reads `backend/profile/resume.md` + job description → rewrites resume for this JD → writes `backend/profile/applications/abc12345/resume_tailored.md`
   - `cover-writer` agent: reads profile + JD + tone preference → writes cover letter → saves to `applications/abc12345/cover_letter.md`
   - `project-matcher` agent: reads `backend/data/projects.md` → selects 2-3 most relevant portfolio projects → writes STAR stories → saves to `project_highlights.md`
4. Orchestrator reports: "Application package ready for [Job Title] at [Company]. Files in backend/profile/applications/abc12345/"

**Scenario: `POST /api/search/run` (batch scraping)**

1. Litestar route handler in `backend/src/routes/search.py` receives scraping parameters (keywords, sources, location)
2. For each source (Indeed, H-E-B, Wellfound): instantiates the corresponding scraper and calls `scrape()`
3. Each scraper uses crawl4ai + Playwright to render JS-heavy job boards; extracts raw HTML
4. `services/parser.py` sends raw HTML to LLM with extraction prompt → returns structured `RawJob` dict
5. `services/scorer.py` scores each job against `backend/data/profile.json` via LLM → returns 0–100 fit score
6. `services/embeddings.py` encodes job text via `all-MiniLM-L6-v2` → stores 384-dim vector to sqlite-vec
7. Job written to `jobs` table; FTS5 virtual table auto-updated; dedup key checked

## 7. Key Technical Decisions & Trade-offs

| Decision | Why | Trade-off accepted | Alternative considered |
|----------|-----|--------------------|----------------------|
| SQLite + sqlite-vec + FTS5 | Single file; zero setup; both semantic and keyword search in one DB | Single-writer; no horizontal scale | PostgreSQL + pgvector — scalable but server management overhead |
| Litestar over FastAPI | Better async DI; cleaner handler signatures; OpenAPI out of box | Smaller ecosystem; fewer StackOverflow answers | FastAPI — more tutorials but more boilerplate |
| Claude Code agents for workflows | Agents run at LLM intelligence level; no custom orchestration code | Requires Claude Code; not independently runnable | Python scripts — more portable but much less capable |
| Local sentence-transformers | Zero cost; no API key; ~90MB model downloaded once | First call slow (model load); 384 dims vs OpenAI 1536 | OpenAI embeddings — higher quality but $0.0001/1K tokens |
| crawl4ai + Playwright | JS-rendered pages (Indeed, Wellfound use React); handles anti-bot with user-agent rotation | Playwright ~500MB install; fragile to DOM changes | requests/BeautifulSoup — can't handle JS-rendered boards |
| Groq as default LLM | Free tier; fast inference for scoring 50+ jobs per session | Lower quality than GPT-4/Claude for complex reasoning | Claude default — higher quality but expensive for high-volume scoring |

## 8. What I'd Improve With More Time

- **No scheduled scraping**: Scraping only runs on demand (`/hunt`). Would add a background scheduler (APScheduler) to run daily during off-hours and notify on new high-fit jobs.
- **LinkedIn scraper is a stub**: LinkedIn's anti-bot measures blocked implementation. Would invest in a proper authenticated scraper or use a data provider (Proxycurl).
- **LLM-parsed job fields are unvalidated**: The parser returns free-form JSON that's trusted on insertion. A malformed parse could insert corrupt data. Would add Pydantic validation with fallback to raw text.
- **Agent outputs aren't version-controlled**: Generated resumes and cover letters overwrite previous versions. Would add a versioning layer (timestamp-suffixed files or git commits).
- **No test coverage on scrapers**: Scraper logic is entirely untested. Would add pytest tests with saved HTML fixtures to prevent silent breakage when job boards change their DOM.

## 9. Interview Talking Points

I built Canopy because job searching for ML roles is a high-volume manual workflow that screams for automation. The architecture has two distinct layers: a conventional full-stack app (Litestar + React + SQLite) for job storage, scoring, and search, and an agentic orchestration layer built entirely in Claude Code slash commands. The most interesting decision was running resume tailoring, cover letter writing, and project matching in parallel — three Opus agents producing independent documents simultaneously, which cuts the application package generation time to the duration of the slowest single call. The thing I'm most proud of is how the `/apply` command composes these agents into a repeatable workflow — it's genuinely how I'm applying to jobs now.

---

**Top 3 patterns:** Orchestrator-Worker (parallel agents), Strategy (LLM provider + scrapers), Service Layer (business logic isolation)

**Top 3 trade-offs:** SQLite vs PostgreSQL (zero setup vs scale), Groq vs Claude (cost vs quality for high-volume scoring), local embeddings vs OpenAI (zero cost vs quality)

**One thing to consider improving:** No scheduled scraping — the system only discovers jobs on demand, so opportunities posted between `/hunt` runs are missed until the next manual trigger.
