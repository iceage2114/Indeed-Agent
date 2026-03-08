# Job Matcher Agent

A LangGraph agent that reads your resume, queries a ChromaDB vector store of pre-embedded job listings, and produces a ranked report of the top matches by cosine similarity.

---

## How It Works

```
START
  |
[parse_resume]        Extract text from resume file, generate structured JSON summary via LLM
  |
[embed_resume]        Embed full resume text via text-embedding-3-small (single API call)
  |
[query_chroma]        ANN search against pre-built ChromaDB collection, hydrate descriptions from SQLite
  |
[generate_report]     Sort by similarity score, write output/report.json and output/report.md
  |
END
```

Job embeddings are never computed at runtime. Run `python chroma_store.py` once after scraping to populate ChromaDB, then again after each new scrape batch.

---

## Setup

```bash
cd job_matcher

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set GITHUB_TOKEN or OPENAI_API_KEY
```

Drop your resume into the `resume/` folder. Supported formats: `.pdf`, `.txt`, `.md`.

---

## Usage

```bash
# 1. Populate ChromaDB (run once, then after new scrapes)
python chroma_store.py

# 2. Run the matcher
python main.py

# Optional flags
python main.py --resume ./resume/my_cv.pdf --top-n 10

# Force re-embed all jobs (after DB changes)
python chroma_store.py --force

# Test ChromaDB with a custom query
python chroma_store.py --test-only --query "python backend engineer" --n 5
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GITHUB_TOKEN` | — | GitHub Models PAT (used as API key for Azure OpenAI endpoint) |
| `OPENAI_API_KEY` | — | Direct OpenAI key (alternative to GITHUB_TOKEN) |
| `DB_PATH` | `../backend/data/jobs.db` | Path to the scraper SQLite database |
| `RESUME_PATH` | `./resume/resume.pdf` | Default resume path |
| `TOP_N_CANDIDATES` | `20` | Number of top matches to retrieve and report |
| `OUTPUT_DIR` | `./output` | Directory for report files |
| `CHROMA_PATH` | `./chroma_db` | Path to the ChromaDB persistent store |

---

## Output

Two files are written to `output/` after each run:

- `report.json` — full structured data for all ranked matches
- `report.md` — Markdown report with summary table and per-job sections

The report is also served by the backend at `GET /api/matches` and displayed in the frontend Top Matches page.

---

## Project Structure

```
job_matcher/
├── config.py                  Settings and path resolution
├── main.py                    CLI entry point
├── chroma_store.py            Populate and test ChromaDB
├── resume/                    Drop resume here (gitignored)
├── output/                    Report output (gitignored)
├── chroma_db/                 ChromaDB persistent store (gitignored)
└── agent/
    ├── state.py               LangGraph TypedDict state schema
    ├── graph.py               Top-level graph assembly
    ├── nodes/
    │   ├── resume_parser.py   Extract text + LLM structured summary
    │   └── report_generator.py  Write JSON and Markdown reports
    └── subgraphs/
        └── retrieval_subgraph.py  Embed resume + ChromaDB query
```

