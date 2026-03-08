# applying/applier.py - Automatically apply to jobs stored in the SQLite database
#
# Usage (run from backend/ directory):
#   python applying/applier.py                  # dry-run: fill forms but stop before submit
#   python applying/applier.py --apply          # actually submit applications
#   python applying/applier.py --easy-only      # only Indeed Easy Apply jobs
#   python applying/applier.py --external-only  # only external ATS jobs
#   python applying/applier.py --limit 10       # stop after N applications

import os
import sys

# Ensure the backend root is on the path when running this script directly.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import argparse
import asyncio
import json
import logging
from typing import Optional

from dotenv import load_dotenv
from playwright.async_api import async_playwright, BrowserContext, Page
from playwright.async_api import TimeoutError as PWTimeout

from config import BASE_DIR, AUTH_STATE_PATH, PROFILE_PATH
from db.database import init_db, get_unapplied_jobs, mark_applied as db_mark_applied

load_dotenv(os.path.join(BASE_DIR, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(BASE_DIR, "logs", "applier.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ATS detection
# ---------------------------------------------------------------------------
ATS_PATTERNS = {
    "greenhouse":      ["boards.greenhouse.io", "grnh.se"],
    "lever":           ["jobs.lever.co", "lever.co"],
    "workday":         ["myworkdayjobs.com", "workday.com"],
    "taleo":           ["taleo.net"],
    "icims":           ["icims.com"],
    "smartrecruiters": ["jobs.smartrecruiters.com"],
    "ashby":           ["jobs.ashbyhq.com", "ashbyhq.com"],
    "breezy":          ["breezy.hr"],
    "jobvite":         ["jobs.jobvite.com", "jobvite.com"],
}


def _detect_ats(url: str) -> str:
    for ats, domains in ATS_PATTERNS.items():
        for d in domains:
            if d in url:
                return ats
    return "generic"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_profile() -> dict:
    if not os.path.exists(PROFILE_PATH):
        logger.error("profile.json not found at %s", PROFILE_PATH)
        sys.exit(1)
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_jobs(easy_only: bool = False, external_only: bool = False, limit: Optional[int] = None) -> list:
    return get_unapplied_jobs(easy_only=easy_only, external_only=external_only, limit=limit)


def _mark_applied(jobs: list, job_id: str) -> None:
    """Write the applied status to the database (the in-memory list is not mutated)."""
    db_mark_applied(job_id)


# ---------------------------------------------------------------------------
# Generic form-fill
# ---------------------------------------------------------------------------

# Mapping of (name/id/placeholder substrings) -> value getter
FIELD_MAP = {
    ("first_name", "firstname", "first name"):                  lambda p: p["first_name"],
    ("last_name",  "lastname",  "last name",  "surname"):       lambda p: p["last_name"],
    ("full_name",  "fullname",  "your name",  "applicant"):     lambda p: f"{p['first_name']} {p['last_name']}",
    ("email",):                                                  lambda p: p["email"],
    ("phone", "telephone", "mobile", "cell"):                   lambda p: p["phone"],
    ("linkedin",):                                               lambda p: p["linkedin"],
    ("github",):                                                 lambda p: p["github"],
    ("portfolio", "website", "personal site", "personal url"):  lambda p: p["portfolio"],
    ("city",):                                                   lambda p: p["address"]["city"],
    ("state", "province"):                                       lambda p: p["address"]["state"],
    ("zip", "postal"):                                           lambda p: p["address"]["zip"],
    ("country",):                                                lambda p: p["address"]["country"],
    ("salary", "compensation", "expected pay", "desired"):       lambda p: p["salary_expectation"],
    ("availab", "start date"):                                   lambda p: p["availability"],
}


async def _fill_generic_form(page: Page, profile: dict) -> int:
    """Best-effort fill for any HTML form. Returns count of fields filled."""
    filled = 0
    selectors = "input[type=text], input[type=email], input[type=tel], input[type=url], textarea"
    inputs = await page.query_selector_all(selectors)

    for inp in inputs:
        try:
            attr_name = (await inp.get_attribute("name") or "").lower()
            attr_id   = (await inp.get_attribute("id")   or "").lower()
            attr_ph   = (await inp.get_attribute("placeholder") or "").lower()
            combined  = f"{attr_name} {attr_id} {attr_ph}"

            for keys, getter in FIELD_MAP.items():
                if any(k in combined for k in keys):
                    value = getter(profile)
                    if value:
                        await inp.click()
                        await inp.fill(str(value))
                        filled += 1
                    break
        except Exception as exc:
            logger.debug("Field fill error: %s", exc)

    return filled


async def _upload_resume(page: Page, profile: dict) -> bool:
    """Attempt to upload resume to any file input on the page."""
    resume_path = profile.get("resume_path", "")
    if not resume_path or not os.path.exists(resume_path):
        logger.warning("    Resume not found at '%s' - skipping upload.", resume_path)
        return False
    try:
        file_input = await page.query_selector("input[type=file]")
        if file_input:
            await file_input.set_input_files(resume_path)
            logger.info("    Resume uploaded from %s", resume_path)
            return True
    except Exception as exc:
        logger.warning("    Resume upload failed: %s", exc)
    return False


# ---------------------------------------------------------------------------
# Indeed Easy Apply
# ---------------------------------------------------------------------------

async def _apply_easy_apply(page: Page, job: dict, profile: dict, dry_run: bool) -> bool:
    """Drive the multi-step Indeed Easy Apply modal."""
    logger.info("  [Easy Apply] Navigating to job page...")
    try:
        await page.goto(job["url"], wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)
    except Exception as exc:
        logger.warning("  Could not load job page: %s", exc)
        return False

    # Click the Apply / Easy Apply button
    apply_selectors = [
        "[data-testid='indeedApplyButton']",
        "span.iaLabel",
        "button[aria-label*='Apply now' i]",
        "button:has-text('Apply now')",
        "button:has-text('Easy Apply')",
    ]
    apply_btn = None
    for sel in apply_selectors:
        apply_btn = await page.query_selector(sel)
        if apply_btn:
            break

    if not apply_btn:
        logger.info("  No Easy Apply button found on job page.")
        return False

    await apply_btn.click()
    await asyncio.sleep(2)

    # Step loop — Indeed Easy Apply has up to ~5 steps
    for step in range(8):
        logger.info("  [Easy Apply] Step %d", step + 1)

        filled = await _fill_generic_form(page, profile)
        logger.info("    Filled %d text field(s).", filled)
        await _upload_resume(page, profile)

        # Check for final Submit button first
        submit_selectors = [
            "button[data-testid='submit-application-button']",
            "button:has-text('Submit your application')",
            "button:has-text('Submit application')",
        ]
        submit_btn = None
        for sel in submit_selectors:
            submit_btn = await page.query_selector(sel)
            if submit_btn:
                break

        if submit_btn:
            if dry_run:
                logger.info("  [DRY RUN] Reached Submit — stopping here.")
                return False
            logger.info("  Submitting...")
            await submit_btn.click()
            await asyncio.sleep(3)
            logger.info("  Application submitted!")
            return True

        # Otherwise click Continue / Next
        next_selectors = [
            "button[data-testid='continue-button']",
            "button:has-text('Continue')",
            "button:has-text('Next')",
        ]
        next_btn = None
        for sel in next_selectors:
            next_btn = await page.query_selector(sel)
            if next_btn:
                break

        if next_btn:
            await next_btn.click()
            await asyncio.sleep(2)
        else:
            logger.info("  No Continue or Submit button — stopping at step %d.", step + 1)
            break

    return False


# ---------------------------------------------------------------------------
# External ATS handlers
# ---------------------------------------------------------------------------

async def _apply_greenhouse(page: Page, profile: dict, dry_run: bool) -> bool:
    logger.info("  [Greenhouse] Filling form...")
    await _fill_generic_form(page, profile)
    await _upload_resume(page, profile)

    cl_el = await page.query_selector("#cover_letter_text")
    if cl_el and profile.get("cover_letter"):
        await cl_el.fill(profile["cover_letter"])

    # EEO dropdowns: select index 0 (usually Decline to self-identify)
    eeo_ids = [
        "job_application_gender",
        "job_application_race",
        "job_application_veteran_status",
        "job_application_disability_status",
    ]
    for field_id in eeo_ids:
        try:
            sel = await page.query_selector(f"#{field_id}")
            if sel:
                await sel.select_option(index=0)
        except Exception:
            pass

    if dry_run:
        logger.info("  [DRY RUN] Reached Submit — stopping here.")
        return False

    submit = await page.query_selector("input#submit_app, input[type=submit]")
    if submit:
        await submit.click()
        await asyncio.sleep(3)
        return True
    return False


async def _apply_lever(page: Page, profile: dict, dry_run: bool) -> bool:
    logger.info("  [Lever] Filling form...")
    await _fill_generic_form(page, profile)
    await _upload_resume(page, profile)

    cl_el = await page.query_selector("textarea[name=comments]")
    if cl_el and profile.get("cover_letter"):
        await cl_el.fill(profile["cover_letter"])

    if dry_run:
        logger.info("  [DRY RUN] Reached Submit — stopping here.")
        return False

    submit = await page.query_selector("[data-qa=btn-submit], button[type=submit]")
    if submit:
        await submit.click()
        await asyncio.sleep(3)
        return True
    return False


async def _apply_generic(page: Page, profile: dict, ats: str, dry_run: bool) -> bool:
    logger.info("  [%s] Filling form with generic strategy...", ats.title())
    filled = await _fill_generic_form(page, profile)
    await _upload_resume(page, profile)
    logger.info("    Filled %d field(s).", filled)

    if dry_run:
        logger.info("  [DRY RUN] Reached Submit — stopping here.")
        return False

    for sel in ["button[type=submit]", "input[type=submit]", "button:has-text('Submit')", "button:has-text('Apply')"]:
        btn = await page.query_selector(sel)
        if btn:
            await btn.click()
            await asyncio.sleep(3)
            return True
    return False


async def _apply_external(page: Page, context: BrowserContext, job: dict, profile: dict, dry_run: bool) -> bool:
    """Follow the 'Apply on company site' link and fill the external ATS form."""
    logger.info("  [External] Navigating to job page...")
    try:
        await page.goto(job["url"], wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)
    except Exception as exc:
        logger.warning("  Could not load job page: %s", exc)
        return False

    # Find the external apply link
    ext_link_selectors = [
        "a[data-jk][target=_blank]",
        "a:has-text('Apply on company site')",
        "a:has-text('Apply on')",
        "a[href*='apply']",
    ]
    ext_url = None
    for sel in ext_link_selectors:
        el = await page.query_selector(sel)
        if el:
            ext_url = await el.get_attribute("href")
            if ext_url:
                break

    if not ext_url:
        logger.info("  Could not find external apply link.")
        return False

    logger.info("  External URL: %s", ext_url)
    ats = _detect_ats(ext_url)
    logger.info("  Detected ATS: %s", ats)

    ext_page = await context.new_page()
    try:
        await ext_page.goto(ext_url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)

        if ats == "greenhouse":
            success = await _apply_greenhouse(ext_page, profile, dry_run)
        elif ats == "lever":
            success = await _apply_lever(ext_page, profile, dry_run)
        else:
            success = await _apply_generic(ext_page, profile, ats, dry_run)
    finally:
        await ext_page.close()

    return success


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    init_db()  # ensure schema exists
    profile = _load_profile()
    dry_run = not args.apply

    if dry_run:
        logger.info("=== DRY RUN — forms will be filled but NOT submitted ===")
        logger.info("=== Pass --apply to actually submit applications.      ===")
    else:
        logger.info("=== LIVE MODE — applications WILL be submitted ===")

    candidates = _load_jobs(
        easy_only=args.easy_only,
        external_only=args.external_only,
        limit=args.limit,
    )

    logger.info("Found %d job(s) to process.", len(candidates))
    if not candidates:
        logger.info("Nothing to do.")
        return

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx_kwargs: dict = dict(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        if os.path.exists(AUTH_STATE_PATH):
            ctx_kwargs["storage_state"] = AUTH_STATE_PATH

        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()

        applied_count = 0
        skipped_count = 0

        for i, job in enumerate(candidates):
            logger.info("---")
            logger.info("[%d/%d] %s @ %s", i + 1, len(candidates), job["title"], job["company"])
            logger.info("  Easy Apply: %s", job.get("easy_apply", False))

            try:
                if job.get("easy_apply", False):
                    success = await _apply_easy_apply(page, job, profile, dry_run)
                else:
                    success = await _apply_external(page, context, job, profile, dry_run)
            except Exception as exc:
                logger.warning("  Unexpected error: %s", exc)
                success = False

            if success:
                applied_count += 1
                _mark_applied(candidates, job["id"])
                logger.info("  Marked as applied.")
            else:
                skipped_count += 1

            await asyncio.sleep(2)

        await browser.close()

    logger.info("=================================================")
    logger.info("Applied: %d  |  Skipped / dry-run: %d", applied_count, skipped_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-apply to jobs in the SQLite database")
    parser.add_argument("--apply", action="store_true",
                        help="Actually submit applications (default is dry-run)")
    parser.add_argument("--easy-only", action="store_true",
                        help="Only attempt Indeed Easy Apply jobs")
    parser.add_argument("--external-only", action="store_true",
                        help="Only attempt external ATS jobs")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of jobs to attempt")
    args = parser.parse_args()
    asyncio.run(run(args))
