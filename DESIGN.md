# Indeed Job Search Agent — App Design

## Overview

A two-part application:
1. **Backend Agent** — scrapes/queries Indeed for jobs in specific fields and writes results to a JSON file.
2. **Frontend** — reads the JSON file and displays all jobs with their titles, descriptions, and locations.

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Backend | Python 3.12 | Strong scraping/automation ecosystem |
| Scraping | `playwright` or `requests` + `BeautifulSoup` | Headless browsing or HTML parsing |
| Scheduling (optional) | `schedule` or cron | Refresh jobs on a timer |
| Data storage | `jobs.json` | Simple, portable, no DB needed |
| Frontend | React (Vite) | Fast, component-based UI |
| Styling | Tailwind CSS | Quick, utility-first styling |
| HTTP bridge (optional) | FastAPI | Serve JSON via REST if frontend needs live data |

---

## Search Parameters

| Field | Indeed Search Query | Radius |
|---|---|---|
| Entry Level Software Engineering | `entry level software engineer` | 100 miles |
| Entry Level Cybersecurity | `entry level cybersecurity` | 100 miles |
| IT Technician | `IT technician` | 100 miles |

> A user-supplied ZIP code or city will anchor the 100-mile radius.

---

## Backend Design

### Folder Structure

```
backend/
├── agent.py           # Main entry point — orchestrates all searches
├── scraper.py         # Indeed scraping logic
├── models.py          # Job dataclass / schema
├── writer.py          # Writes/updates jobs.json
├── config.py          # Search terms, radius, location, output path
├── requirements.txt
└── jobs.json          # Output file (generated)
```

### Data Flow

```
agent.py
  └── for each search field:
        └── scraper.py  →  fetches Indeed results (paginated)
              └── parses: title, company, location, description, URL, date posted
        └── writer.py   →  merges results into jobs.json
```

### Job Schema (`jobs.json`)

```json
[
  {
    "id": "unique_hash_of_url",
    "title": "Junior Software Engineer",
    "company": "Acme Corp",
    "location": "Austin, TX",
    "description": "We are looking for...",
    "url": "https://www.indeed.com/viewjob?jk=...",
    "date_posted": "2026-03-01",
    "field": "entry level software engineering",
    "scraped_at": "2026-03-04T12:00:00"
  }
]
```

### Scraper Strategy

1. **Indeed URL pattern:**
   ```
   https://www.indeed.com/jobs?q=<query>&l=<location>&radius=100
   ```
2. Use `playwright` (headless Chrome) to handle JavaScript-rendered pages and avoid bot detection.
3. Paginate through results (Indeed shows ~15 jobs/page) — stop after N pages or when no new jobs are found.
4. For each job card, click through or parse the inline description panel to get the full description text.
5. Deduplicate by job URL before writing to `jobs.json`.

### Key Considerations

- **Rate limiting** — Add random delays (1–3s) between requests to avoid being blocked.
- **User-Agent rotation** — Rotate realistic browser user-agent strings.
- **Error handling** — Log failed pages and continue; retry up to 3 times.
- **Incremental updates** — On re-run, only add new jobs not already in `jobs.json` (compare by `id`).

---

## Frontend Design

### Folder Structure

```
frontend/
├── public/
│   └── jobs.json          # Copied/served from backend output
├── src/
│   ├── App.jsx            # Root component
│   ├── components/
│   │   ├── JobCard.jsx    # Single job display
│   │   ├── JobList.jsx    # Renders list of JobCards
│   │   ├── FilterBar.jsx  # Filter by field, location, keyword
│   │   └── Header.jsx     # App title + stats
│   ├── hooks/
│   │   └── useJobs.js     # Fetches and filters jobs.json
│   └── main.jsx
├── tailwind.config.js
├── vite.config.js
└── package.json
```

### Page Layout

```
┌─────────────────────────────────────────────────┐
│  Header: "Indeed Job Board"  |  X jobs found     │
├─────────────────────────────────────────────────┤
│  FilterBar: [Field ▼]  [Location 🔍]  [Keyword] │
├─────────────────────────────────────────────────┤
│  ┌───────────────────┐  ┌───────────────────┐   │
│  │  Job Card          │  │  Job Card          │   │
│  │  Title             │  │  Title             │   │
│  │  Company | Location│  │  Company | Location│   │
│  │  Field tag         │  │  Field tag         │   │
│  │  Description       │  │  Description       │   │
│  │  [View on Indeed]  │  │  [View on Indeed]  │   │
│  └───────────────────┘  └───────────────────┘   │
│  ...                                             │
└─────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| `App.jsx` | Load `jobs.json`, manage filter state, pass data down |
| `Header.jsx` | Show app title and total job count |
| `FilterBar.jsx` | Dropdowns/inputs to filter by field, keyword, location |
| `JobList.jsx` | Map filtered jobs array to `JobCard` components |
| `JobCard.jsx` | Display title, company, location, field tag, truncated description with expand toggle, link to Indeed |
| `useJobs.js` | `fetch('/jobs.json')`, return jobs + loading/error state |

### Filtering Logic

- **Field** — filter by `job.field` value (dropdown: All / Software Engineering / Cybersecurity / IT Technician)
- **Keyword** — case-insensitive match against `title` + `description`
- **Location** — case-insensitive match against `job.location`
- Filters are applied client-side on the in-memory array.

---

## Integration: How Backend Feeds Frontend

### Option A — Static File (Simple)

1. Backend writes `jobs.json` to `frontend/public/jobs.json`.
2. Vite serves it as a static asset.
3. Frontend fetches `/jobs.json` on load.
4. Re-run the backend agent to refresh the data.

### Option B — FastAPI Bridge (Live)

```
backend/
└── api.py   # FastAPI app, serves GET /api/jobs from jobs.json
```

1. Backend exposes `GET /api/jobs` (optionally filtered by `?field=&location=`).
2. Frontend fetches from `http://localhost:8000/api/jobs`.
3. CORS enabled for local dev.
4. Supports adding a "Refresh Jobs" button that triggers `POST /api/refresh` to re-run the scraper.

> **Recommended:** Start with Option A. Upgrade to Option B if you want a refresh button or server-side filtering.

---

## Development Phases

| Phase | Tasks |
|---|---|
| 1 | Set up Python backend, install `playwright`, write `config.py` and `scraper.py` |
| 2 | Implement `writer.py` and `models.py`, verify `jobs.json` output |
| 3 | Wire up `agent.py` to run all three field searches |
| 4 | Scaffold Vite + React frontend with Tailwind |
| 5 | Build `useJobs.js`, `JobCard.jsx`, `JobList.jsx` |
| 6 | Build `FilterBar.jsx` and wire up filtering |
| 7 | Connect backend JSON output to frontend (Option A or B) |
| 8 | Polish UI, error states, loading spinners, empty states |

---

## Future Enhancements

- Store jobs in SQLite instead of flat JSON for faster querying.
- Schedule the agent to run nightly with Windows Task Scheduler or a cron job.
- Add a "saved jobs" feature using `localStorage`.
- Email alerts for new jobs matching saved searches.
- Proxy rotation to reduce scraping blocks.
