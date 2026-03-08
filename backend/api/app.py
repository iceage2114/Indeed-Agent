# api/app.py — FastAPI application; serves job data from the SQLite database

import json
import os
import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware

from config import LOCATIONS, SCRAPE_INTERVAL_HOURS, SCRAPE_ON_STARTUP, BASE_DIR
from db.database import init_db, get_jobs, get_applied_jobs, job_count, mark_applied, unmark_applied, delete_job, wipe_jobs

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Indeed Job Agent API", version="1.0.0")
scheduler = AsyncIOScheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/locations")
def get_locations():
    """Return all configured scrape locations."""
    logger.debug("GET /api/locations -> %d locations", len(LOCATIONS))
    return LOCATIONS


@app.on_event("startup")
async def on_startup():
    """Initialise DB schema and start the background scrape scheduler."""
    logger.info("Starting up — initialising database.")
    init_db()
    logger.info("Database initialised.")
    scheduler.add_job(
        _run_refresh,
        trigger="interval",
        hours=SCRAPE_INTERVAL_HOURS,
        id="scheduled_scrape",
        replace_existing=True,
        next_run_time=datetime.now() if SCRAPE_ON_STARTUP else None,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — scraping every %d hour(s). Startup scrape: %s.",
        SCRAPE_INTERVAL_HOURS,
        "enabled" if SCRAPE_ON_STARTUP else "disabled",
    )


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown(wait=False)


@app.get("/api/jobs")
def get_jobs_endpoint(
    field: Optional[str] = Query(None, description="Filter by field label"),
    location: Optional[str] = Query(None, description="Filter by location substring"),
    keyword: Optional[str] = Query(None, description="Search title + description"),
):
    logger.debug("GET /api/jobs  field=%r  location=%r  keyword=%r", field, location, keyword)
    results = get_jobs(field=field, location=location, keyword=keyword)
    logger.debug("GET /api/jobs  -> %d results", len(results))
    return results


@app.get("/api/jobs/applied")
def get_applied_endpoint():
    return get_applied_jobs()


@app.post("/api/jobs/{job_id}/apply")
def apply_job(job_id: str):
    mark_applied(job_id)
    return {"status": "ok"}


@app.delete("/api/jobs/{job_id}/apply")
def unapply_job(job_id: str):
    unmark_applied(job_id)
    return {"status": "ok"}


@app.delete("/api/jobs/{job_id}")
def dismiss_job(job_id: str):
    delete_job(job_id)
    return {"status": "ok"}


@app.delete("/api/jobs")
def wipe_all_jobs():
    """Delete every job from the database."""
    deleted = wipe_jobs()
    logger.info("Wiped %d jobs from the database.", deleted)
    return {"status": "ok", "deleted": deleted}


@app.get("/api/matches")
def get_matches():
    """Return the top-match report produced by the job_matcher agent."""
    report_path = os.path.join(BASE_DIR, "..", "job_matcher", "output", "report.json")
    report_path = os.path.normpath(report_path)
    if not os.path.exists(report_path):
        return {"error": "No report found. Run python main.py in job_matcher first.", "matches": []}
    try:
        with open(report_path, encoding="utf-8") as f:
            matches = json.load(f)
        return {"matches": matches}
    except Exception as exc:
        logger.error("Failed to read report.json: %s", exc)
        return {"error": str(exc), "matches": []}


_refresh_running = False


def _run_scraper_subprocess() -> int:
    """Blocking: spawn agent.py in a child process and stream its output to our logger."""
    import subprocess
    import sys

    logger.info("Spawning scraper subprocess: scraping/agent.py")
    proc = subprocess.Popen(
        [sys.executable, "scraping/agent.py"],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in proc.stdout:
        logger.info("[scraper] %s", line.rstrip())
    proc.wait()
    logger.info("Scraper subprocess exited with code %d", proc.returncode)
    return proc.returncode


async def _run_refresh():
    global _refresh_running
    if _refresh_running:
        logger.warning("_run_refresh called while already running — skipping.")
        return
    _refresh_running = True
    logger.info("=== Scrape refresh started ===")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run_scraper_subprocess)
    except Exception as exc:
        logger.error("Fatal error during refresh: %s", exc, exc_info=True)
    finally:
        _refresh_running = False
        logger.info("=== Scrape refresh complete ===")


@app.post("/api/refresh")
async def refresh_jobs(background_tasks: BackgroundTasks):
    if _refresh_running:
        logger.info("POST /api/refresh — already running, skipping.")
        return {"status": "already_running"}
    logger.info("POST /api/refresh — queuing background scrape task.")
    background_tasks.add_task(_run_refresh)
    return {"status": "started"}


@app.get("/api/status")
def status():
    job = scheduler.get_job("scheduled_scrape")
    return {
        "refresh_running": _refresh_running,
        "job_count": job_count(),
        "next_scrape": job.next_run_time.isoformat() if job and job.next_run_time else None,
    }
