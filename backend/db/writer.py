# db/writer.py — Persists scraped jobs to the SQLite database

import logging
from typing import List

from db.models import Job
from db.database import upsert_jobs

logger = logging.getLogger(__name__)


def merge_and_save(new_jobs: List[Job]) -> int:
    """
    Upsert new_jobs into the SQLite database.
    Duplicate jobs (same URL/id) are silently skipped.
    Returns the number of *new* jobs inserted.
    """
    added = upsert_jobs(new_jobs)
    logger.info("Inserted %d new job(s) into the database.", added)
    return added
