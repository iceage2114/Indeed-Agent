# Indeed Job Agent

An autonomous job-hunting pipeline. Scrapes Indeed with Playwright, stores listings in SQLite, surfaces them through a React + FastAPI interface, and uses a LangGraph agent with ChromaDB vector search to rank the best matches against your resume.

---

## Components

| Directory | Purpose |
|---|---|
| `backend/` | FastAPI REST API, Playwright scraper, APScheduler, SQLite |
| `frontend/` | React + Tailwind job board UI |
| `job_matcher/` | LangGraph agent — resume parsing, vector retrieval, match report |

---

## Quick Start (Local)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
playwright install chromium
uvicorn api.app:app --reload
```

API available at http://localhost:8000.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI available at http://localhost:5173. The Vite dev server proxies `/api/*` to the backend automatically.

### Scraper (manual run)

```bash
cd backend
python scraping/agent.py
```

The scheduler also triggers a scrape automatically on the configured interval.

---

## Quick Start (Docker)

```bash
# Start backend and frontend
docker compose up --build

# Populate ChromaDB with job embeddings (run once, then after new scrapes)
docker compose run --rm --profile matcher job_matcher python chroma_store.py

# Run the job matcher agent
docker compose run --rm --profile matcher job_matcher
```

Frontend at http://localhost:5173, API at http://localhost:8000.

---

## Configuration

**`backend/config.py`**

| Setting | Description |
|---|---|
| `LOCATIONS` | List of ZIP codes or city names to search |
| `RADIUS` | Search radius in miles |
| `SEARCH_FIELDS` | Job query terms and labels |
| `SCRAPE_INTERVAL_HOURS` | How often the background scraper runs |
| `SCRAPE_ON_STARTUP` | Run a scrape immediately on server start |

**`job_matcher/.env`** (copy from `.env.example`)

| Variable | Default | Description |
|---|---|---|
| `GITHUB_TOKEN` | — | GitHub Models PAT used as the OpenAI-compatible API key |
| `OPENAI_API_KEY` | — | Direct OpenAI key (alternative to GITHUB_TOKEN) |
| `DB_PATH` | `../backend/data/jobs.db` | Path to the SQLite database |
| `TOP_N_CANDIDATES` | `20` | Number of top matches to retrieve and report |
| `CHROMA_PATH` | `./chroma_db` | Path to the ChromaDB persistent store |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/jobs` | List unapplied jobs (`?field=`, `?location=`, `?keyword=`) |
| `GET` | `/api/jobs/applied` | List applied jobs |
| `POST` | `/api/jobs/{id}/apply` | Mark job as applied |
| `DELETE` | `/api/jobs/{id}/apply` | Unmark applied |
| `DELETE` | `/api/jobs/{id}` | Delete a job |
| `GET` | `/api/matches` | Return top-match report from job_matcher output |
| `POST` | `/api/refresh` | Trigger a background scrape |
| `GET` | `/api/status` | Scraper status and job count |

---

## Project Structure

```
indeed_agent/
├── Dockerfile                  Multi-stage build (backend / frontend / job_matcher targets)
├── docker-compose.yml
├── .gitignore
├── .dockerignore
├── backend/
│   ├── requirements.txt
│   ├── config.py
│   ├── api/app.py              FastAPI routes
│   ├── scraping/
│   │   ├── agent.py            Scrape orchestrator
│   │   └── scraper.py          Playwright Indeed scraper
│   ├── applying/
│   │   └── applier.py          Auto-apply bot
│   ├── db/
│   │   ├── database.py         SQLite helpers
│   │   ├── models.py           Job dataclass
│   │   └── writer.py           DB upsert logic
│   └── data/
│       ├── jobs.db             SQLite database (auto-created, gitignored)
│       └── profile.json        Personal info for auto-applier (gitignored)
├── frontend/
│   ├── nginx.conf
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── Header.jsx
│           ├── FilterBar.jsx
│           ├── JobList.jsx
│           ├── JobCard.jsx
│           ├── AppliedPanel.jsx
│           └── TopMatchesPage.jsx
└── job_matcher/
    ├── requirements.txt
    ├── config.py
    ├── main.py                 CLI entry point
    ├── chroma_store.py         Populate and test ChromaDB
    ├── resume/                 Drop resume here (gitignored)
    ├── output/                 Report output (gitignored)
    ├── chroma_db/              ChromaDB persistent store (gitignored)
    └── agent/
        ├── graph.py
        ├── state.py
        ├── nodes/
        │   ├── resume_parser.py
        │   └── report_generator.py
        └── subgraphs/
            └── retrieval_subgraph.py
```
