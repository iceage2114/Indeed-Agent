# db/database.py — SQLite persistence layer for jobs

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Optional

from config import JOBS_DB_PATH
from db.models import Job


@contextmanager
def _get_conn():
    conn = sqlite3.connect(JOBS_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the jobs table and indexes if they don't already exist."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT    PRIMARY KEY,
                title       TEXT    NOT NULL DEFAULT '',
                company     TEXT    NOT NULL DEFAULT '',
                location    TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                url         TEXT    UNIQUE NOT NULL,
                date_posted TEXT    NOT NULL DEFAULT '',
                field       TEXT    NOT NULL DEFAULT '',
                scraped_at  TEXT    NOT NULL DEFAULT '',
                easy_apply  INTEGER NOT NULL DEFAULT 0,
                applied     INTEGER NOT NULL DEFAULT 0,
                applied_at  TEXT    NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_field   ON jobs (field);
            CREATE INDEX IF NOT EXISTS idx_jobs_applied ON jobs (applied);
            CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs (scraped_at);
        """)


def upsert_jobs(jobs: List[Job]) -> int:
    """
    Insert new jobs into the DB, silently skipping any whose id already exists.
    Returns the count of newly inserted rows.
    """
    added = 0
    with _get_conn() as conn:
        for job in jobs:
            d = job.to_dict()
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO jobs
                    (id, title, company, location, description, url,
                     date_posted, field, scraped_at, easy_apply, applied, applied_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    d["id"], d["title"], d["company"], d["location"],
                    d["description"], d["url"], d["date_posted"], d["field"],
                    d["scraped_at"], int(d["easy_apply"]), int(d["applied"]),
                    d["applied_at"],
                ),
            )
            added += cur.rowcount
    return added


def get_jobs(
    field: Optional[str] = None,
    location: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[dict]:
    """Return non-applied jobs as dicts, newest first, with optional filters."""
    clauses: List[str] = ["applied = 0"]
    params: List[str] = []

    if field:
        clauses.append("field LIKE ?")
        params.append(f"%{field}%")
    if location:
        clauses.append("location LIKE ?")
        params.append(f"%{location}%")
    if keyword:
        clauses.append("(title LIKE ? OR description LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    sql = "SELECT * FROM jobs WHERE " + " AND ".join(clauses)
    sql += " ORDER BY scraped_at DESC"

    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_unapplied_jobs(
    easy_only: bool = False,
    external_only: bool = False,
    limit: Optional[int] = None,
) -> List[dict]:
    """Return unapplied jobs for the applier, with optional filters."""
    sql = "SELECT * FROM jobs WHERE applied = 0"
    if easy_only:
        sql += " AND easy_apply = 1"
    elif external_only:
        sql += " AND easy_apply = 0"
    sql += " ORDER BY scraped_at DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    with _get_conn() as conn:
        rows = conn.execute(sql).fetchall()
        return [_row_to_dict(r) for r in rows]


def mark_applied(job_id: str) -> None:
    """Stamp a job as applied with the current UTC time."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET applied = 1, applied_at = ? WHERE id = ?",
            (now, job_id),
        )


def unmark_applied(job_id: str) -> None:
    """Clear the applied flag, returning the job to the main list."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET applied = 0, applied_at = '' WHERE id = ?",
            (job_id,),
        )


def delete_job(job_id: str) -> None:
    """Permanently remove a job from the database."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


def get_applied_jobs() -> List[dict]:
    """Return all jobs marked as applied, newest applied_at first."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE applied = 1 ORDER BY applied_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def url_exists(url: str) -> bool:
    """Return True if a job with this URL is already in the database."""
    with _get_conn() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE url = ? LIMIT 1", (url,)).fetchone()
        return row is not None


def wipe_jobs() -> int:
    """Delete every row from the jobs table. Returns the number of rows deleted."""
    with _get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.execute("DELETE FROM jobs")
    return count


def job_count() -> int:
    with _get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["easy_apply"] = bool(d["easy_apply"])
    d["applied"] = bool(d["applied"])
    return d
