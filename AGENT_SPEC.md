# Job Matcher Agent — GitHub Copilot Project Spec

## Overview

Build a LangGraph-powered agentic retrieval app called **`job_matcher`** that reads a user's resume, compares it against job postings stored in the existing Indeed-scraper SQLite database, selects the 5-10 best matches, fetches the full job detail pages from Indeed for those matches, and produces a ranked report with match reasoning.

The project lives at the **same root level** as `backend/` and `frontend/`:

```
indeed_agent/
├── backend/          ← existing Indeed scraper + API
├── frontend/         ← existing React UI
└── job_matcher/      ← NEW — this project
```

---

## Folder Structure to Create

```
job_matcher/
├── .env.example
├── README.md
├── requirements.txt
├── config.py
├── main.py                        ← CLI entry point
├── resume/
│   └── .gitkeep                   ← user drops resume.pdf or resume.txt here
├── output/
│   └── .gitkeep                   ← JSON + Markdown reports written here
└── agent/
    ├── __init__.py
    ├── state.py                   ← LangGraph TypedDict state schema
    ├── graph.py                   ← top-level StateGraph assembly
    ├── nodes/
    │   ├── __init__.py
    │   ├── resume_parser.py       ← extract text + structured skills from resume
    │   └── report_generator.py   ← compile final ranked Markdown + JSON report
    └── subgraphs/
        ├── __init__.py
        ├── retrieval_subgraph.py  ← embed resume + DB jobs → top-N candidates
        └── enrichment_subgraph.py ← scrape job URLs → deep LLM comparison
```

---

## Technology Stack

| Concern | Library |
|---|---|
| Agent workflow | `langgraph >= 0.2` |
| LLM calls | `langchain-openai` (GPT-4o via GitHub Models or OpenAI key) |
| Embeddings | `langchain-openai` — `text-embedding-3-small` |
| Vector similarity | `numpy` cosine similarity (no external vector DB needed) |
| Resume PDF parsing | `pypdf` |
| Job page scraping | `playwright` (async, reuse headless pattern from `../backend/scraping/scraper.py`) |
| Database | `sqlite3` (stdlib) — reads existing DB at `../backend/data/jobs.db` |
| Environment | `python-dotenv` |
| Output | `json`, `pathlib` |

---

## Environment Variables (`.env.example`)

```env
# Required: GitHub Models PAT  OR  OpenAI API key
GITHUB_TOKEN=your_github_pat_here
# OPENAI_API_KEY=sk-...    ← alternative: comment out GITHUB_TOKEN and use this

# Optional overrides
DB_PATH=../backend/data/jobs.db
RESUME_PATH=./resume/resume.pdf
TOP_N_CANDIDATES=10
OUTPUT_DIR=./output
```

---

## `config.py`

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR    = Path(__file__).parent
DB_PATH     = Path(os.getenv("DB_PATH",     BASE_DIR / "../backend/data/jobs.db")).resolve()
RESUME_PATH = Path(os.getenv("RESUME_PATH", BASE_DIR / "resume/resume.pdf")).resolve()
OUTPUT_DIR  = Path(os.getenv("OUTPUT_DIR",  BASE_DIR / "output")).resolve()
TOP_N       = int(os.getenv("TOP_N_CANDIDATES", 10))

GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Use GitHub Models endpoint unless a direct OpenAI key is set
LLM_BASE_URL = "https://models.inference.ai.azure.com"
LLM_MODEL    = "gpt-4o"
EMBED_MODEL  = "text-embedding-3-small"
```

---

## State Schema (`agent/state.py`)

```python
from typing import TypedDict, Optional

class JobCandidate(TypedDict):
    id: str
    title: str
    company: str
    location: str
    description: str            # short description pulled from DB
    url: str
    date_posted: str
    field: str
    easy_apply: bool
    embedding: Optional[list]           # set during retrieval subgraph
    similarity_score: Optional[float]   # cosine similarity vs resume embedding
    full_description: Optional[str]     # scraped from the live job URL
    match_score: Optional[int]          # 1-100, assigned by LLM in enrichment
    match_reasoning: Optional[str]      # LLM explanation of score
    top_skills_matched: Optional[list]  # list[str] extracted by LLM

class AgentState(TypedDict):
    resume_path: str
    resume_text: str                    # raw text extracted from resume file
    resume_embedding: list              # embedding vector of full resume text
    resume_summary: str                 # LLM-structured JSON summary of resume
    all_jobs: list                      # list[JobCandidate] loaded from DB
    top_candidates: list                # list[JobCandidate] after similarity rank
    enriched_matches: list              # list[JobCandidate] after URL scrape + LLM
    final_report_path: str
    error: Optional[str]
```

---

## LangGraph Graph Design (`agent/graph.py`)

### Top-Level Graph

```
START
  |
  v
[parse_resume]           — reads resume file, extracts text, calls LLM for summary
  |
  v
[retrieval_subgraph]     — subgraph: load DB jobs, embed all, rank by cosine similarity
  |
  v
[enrichment_subgraph]    — subgraph: scrape each top candidate URL, LLM deep compare
  |
  v
[generate_report]        — writes ranked Markdown + JSON to output/
  |
  v
END
```

Assemble the graph like this:

```python
from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes.resume_parser import parse_resume
from agent.nodes.report_generator import generate_report
from agent.subgraphs.retrieval_subgraph import build_retrieval_subgraph
from agent.subgraphs.enrichment_subgraph import build_enrichment_subgraph

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("parse_resume",  parse_resume)
    graph.add_node("retrieval",     build_retrieval_subgraph().compile())
    graph.add_node("enrichment",    build_enrichment_subgraph().compile())
    graph.add_node("generate_report", generate_report)

    graph.add_edge(START, "parse_resume")
    graph.add_conditional_edges(
        "parse_resume",
        lambda s: END if s.get("error") else "retrieval",
    )
    graph.add_edge("retrieval",  "enrichment")
    graph.add_edge("enrichment", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()
```

---

## Retrieval Subgraph (`agent/subgraphs/retrieval_subgraph.py`)

### Sub-state

```python
class RetrievalState(TypedDict):
    resume_text: str
    resume_embedding: list
    all_jobs: list          # list[JobCandidate]
    top_candidates: list    # list[JobCandidate]
```

### Nodes

**`load_jobs_from_db(state)`**
- Open `DB_PATH` read-only with `sqlite3.connect(str(DB_PATH))`.
- Query: `SELECT id, title, company, location, description, url, date_posted, field, easy_apply FROM jobs WHERE applied = 0`
- Map each row to a `JobCandidate` dict (set optional fields to `None`).
- Return `{"all_jobs": [...]}`

**`embed_resume(state)`**
- Use `langchain_openai.OpenAIEmbeddings(model=EMBED_MODEL, api_key=api_key, base_url=LLM_BASE_URL)`.
- Embed `state["resume_text"]`.
- Return `{"resume_embedding": vector}`

**`embed_jobs(state)`**
- Batch-embed all job `description` fields in groups of 100.
- Attach `embedding` to each job candidate.
- Return `{"all_jobs": updated_list}`

**`rank_by_similarity(state)`**
- Compute cosine similarity between `resume_embedding` and each job `embedding` using numpy.
- Sort descending, keep top `TOP_N`.
- Attach `similarity_score` to each selected candidate.
- Return `{"top_candidates": top_n_list}`

### Edges
`START → load_jobs_from_db → embed_resume → embed_jobs → rank_by_similarity → END`

---

## Enrichment Subgraph (`agent/subgraphs/enrichment_subgraph.py`)

### Sub-state

```python
class EnrichmentState(TypedDict):
    resume_summary: str
    top_candidates: list    # list[JobCandidate]
    enriched_matches: list  # list[JobCandidate]
```

### Nodes

**`scrape_job_pages(state)`**
- Use `playwright.sync_api.sync_playwright` in headless Chromium mode.
- For each candidate in `top_candidates`:
  - Navigate to `candidate["url"]`.
  - Try selector `#jobDescriptionText`, fallback to `div[data-testid="jobsearch-JobComponent-description"]`, fallback to joining all `<p>` and `<li>` inner texts.
  - Random delay 2-4 seconds between page loads.
  - On failure after 2 retries, use `candidate["description"]` as `full_description`.
- Return `{"top_candidates": updated_with_full_description}`

**`deep_compare(state)`**
- For each candidate in `top_candidates`:
  - Call GPT-4o with:
    - system: "You are a senior technical recruiter. Score how well this candidate fits this job posting. Return ONLY valid JSON: {\"match_score\": <int 1-100>, \"match_reasoning\": \"<string>\", \"top_skills_matched\": [\"<string>\"]}"
    - user: "RESUME SUMMARY:\n{resume_summary}\n\nJOB DESCRIPTION:\n{full_description}"
  - Parse JSON response.
  - Attach `match_score`, `match_reasoning`, `top_skills_matched` to candidate.
- Return `{"enriched_matches": updated_list}`

### Edges
`START → scrape_job_pages → deep_compare → END`

---

## Node Implementations

### `agent/nodes/resume_parser.py`

```python
# parse_resume(state: AgentState) -> dict
#
# 1. Read state["resume_path"]. If not found, return {"error": "Resume file not found: {path}"}
# 2. Detect extension:
#      .pdf  → use pypdf.PdfReader; join page.extract_text() for all pages
#      .txt  → open(path).read()
#      .md   → open(path).read()
#      other → return {"error": "Unsupported resume format: {ext}"}
# 3. Store raw text in resume_text.
# 4. LLM call (non-streaming):
#      system: "Extract a structured summary from this resume. Return ONLY valid JSON with
#               keys: name, contact, years_experience, tech_skills (list), soft_skills (list),
#               education (list), certifications (list), target_roles (list), profile (str)."
#      user:   resume_text
# 5. Return {"resume_text": ..., "resume_summary": llm_json_string, "error": None}
```

### `agent/nodes/report_generator.py`

```python
# generate_report(state: AgentState) -> dict
#
# 1. Sort state["enriched_matches"] by match_score descending.
# 2. Create OUTPUT_DIR if it does not exist.
# 3. Write OUTPUT_DIR/report.json  — json.dumps(enriched_matches, indent=2)
# 4. Write OUTPUT_DIR/report.md with format:
#
#    # Job Match Report
#    Generated: {datetime}
#    Resume: {resume_path}
#
#    ## Summary Table
#    | Rank | Title | Company | Location | Score | Easy Apply | Date Posted |
#    |------|-------|---------|----------|-------|------------|-------------|
#    | 1    | ...   | ...     | ...      | 94    | Yes        | ...         |
#
#    ---
#
#    ## #1 — {title} at {company} ({location})
#    **Match Score**: {match_score}/100
#    **Easy Apply**: Yes/No
#    **Field**: {field}
#    **Date Posted**: {date_posted}
#    **URL**: {url}
#    **Top Skills Matched**: {", ".join(top_skills_matched)}
#    **Reasoning**: {match_reasoning}
#
# 5. Print summary table to stdout.
# 6. Return {"final_report_path": str(OUTPUT_DIR / "report.md")}
```

---

## CLI Entry Point (`main.py`)

```python
# Usage examples:
#   python main.py
#   python main.py --resume ./resume/my_cv.pdf
#   python main.py --resume ./resume/my_cv.pdf --top-n 7
#
# Steps:
# 1. argparse: --resume (default: config.RESUME_PATH), --top-n (default: config.TOP_N)
# 2. Override config values with CLI args.
# 3. Verify the resume file exists before invoking the graph.
# 4. Build initial AgentState:
#      {"resume_path": str(resume_path), "resume_text": "", "resume_embedding": [],
#       "resume_summary": "", "all_jobs": [], "top_candidates": [],
#       "enriched_matches": [], "final_report_path": "", "error": None}
# 5. from agent.graph import build_graph; app = build_graph()
# 6. result = app.invoke(initial_state)
# 7. If result.get("error"): print(f"ERROR: {result['error']}"); sys.exit(1)
# 8. print(f"\nReport saved to: {result['final_report_path']}")
```

---

## `requirements.txt`

```
langgraph>=0.2.0
langchain>=0.2.0
langchain-openai>=0.1.0
openai>=1.30.0
pypdf>=4.0.0
playwright>=1.44.0
numpy>=1.26.0
python-dotenv>=1.0.0
```

---

## Key Implementation Constraints

1. **Do not modify any existing files** in `backend/` or `frontend/`.
2. Read the SQLite DB **read-only** — never write to it from this project.
3. LangGraph nodes are synchronous. Wrap all async Playwright calls in a helper:
   ```python
   import asyncio
   def run_async(coro):
       return asyncio.get_event_loop().run_until_complete(coro)
   ```
   Alternatively, use `playwright.sync_api.sync_playwright` to avoid async entirely.
4. The OpenAI/LangChain client must be configured to use `GITHUB_TOKEN` as the API key
   and `LLM_BASE_URL` as the `base_url` when `OPENAI_API_KEY` is not set.
   Pattern from `test1.py`:
   ```python
   api_key = config.OPENAI_API_KEY or config.GITHUB_TOKEN
   base_url = None if config.OPENAI_API_KEY else config.LLM_BASE_URL
   ```
5. If the DB has fewer jobs than `TOP_N`, return all available jobs — no error.
6. Node functions must return a **new dict** with only the changed keys — never mutate state in-place.
7. Add a top-level `try/except` in `main.py` so any unhandled exception prints a clean message and exits with code 1.

---

## Setup Instructions (include in project README)

```bash
# 1. Navigate into the new folder
cd job_matcher

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Copy env file and add your GitHub PAT
copy .env.example .env
# edit .env — set GITHUB_TOKEN=your_pat_here

# 5. Drop your resume into the resume/ folder
# Supported formats: .pdf, .txt, .md

# 6. Run
python main.py
# or with overrides:
python main.py --resume ./resume/my_resume.pdf --top-n 7
```

---

## Expected Output

After a successful run, `output/report.md` contains:

```markdown
# Job Match Report
Generated: 2026-03-07 14:32:00
Resume: resume.pdf

## Summary Table
| Rank | Title | Company | Location | Score | Easy Apply | Date Posted |
|------|-------|---------|----------|-------|------------|-------------|
| 1    | Software Engineer | Acme Corp | Seattle, WA | 94 | Yes | 2026-03-01 |
| 2    | Backend Developer | Beta Inc  | Remote      | 87 | No | 2026-03-05 |

---

## #1 — Software Engineer at Acme Corp (Seattle, WA)
**Match Score**: 94/100
**Easy Apply**: Yes
**Field**: entry level software engineering
**Date Posted**: 2026-03-01
**URL**: https://www.indeed.com/viewjob?jk=abc123
**Top Skills Matched**: Python, REST APIs, system design, Git
**Reasoning**: The candidate has 2 years of Python experience and multiple REST API
projects that directly match the core requirements. System design coursework aligns
with the senior guidance expected in this role.
```
