# scraping/scraper.py - Indeed scraping logic using Playwright

import asyncio
import logging
import os
import random
from datetime import datetime
from typing import List
from urllib.parse import urlencode, urljoin

from dotenv import load_dotenv
from playwright.async_api import BrowserContext, Page, TimeoutError as PWTimeout

from config import (
    RADIUS,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    MAX_PAGES_PER_FIELD,
    MAX_NEW_JOBS_PER_FIELD,
    MAX_RETRIES,
    BASE_DIR,
    AUTH_STATE_PATH,
    BLOCKED_COMPANIES,
)
from db.database import url_exists
from db.models import Job

load_dotenv(os.path.join(BASE_DIR, ".env"))

logger = logging.getLogger(__name__)

INDEED_BASE = "https://www.indeed.com"
GOOGLE_EMAIL = os.environ["GOOGLE_EMAIL"]
GOOGLE_PASSWORD = os.environ["GOOGLE_PASSWORD"]


def _build_url(query: str, location: str, start: int = 0) -> str:
    params = {"q": query, "l": location, "radius": str(RADIUS), "start": str(start)}
    url = f"{INDEED_BASE}/jobs?{urlencode(params)}"
    logger.debug("Built URL: %s", url)
    return url


async def _random_delay() -> None:
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    logger.debug("Waiting %.1fs...", delay)
    await asyncio.sleep(delay)


async def _sign_in_google(page: Page) -> None:
    """Click the Google sign-in button on Indeed and complete the OAuth flow."""
    logger.info("Starting Google sign-in flow...")

    # --- Click the Google button on Indeed ---
    google_btn_selectors = [
        "button[data-tn-element='google']",
        "a[data-tn-element='google']",
        "button[aria-label*='Google']",
        "a[aria-label*='Google']",
    ]

    # Try to find and click the Google button; it may open a popup
    google_page = None
    for sel in google_btn_selectors:
        el = await page.query_selector(sel)
        if el:
            try:
                async with page.expect_popup(timeout=8_000) as popup_info:
                    await el.click()
                google_page = await popup_info.value
                logger.info("Google popup opened.")
            except PWTimeout:
                # No popup - may have navigated in same tab
                google_page = page
                logger.info("No popup - using same tab.")
            break

    if google_page is None:
        # Fallback: look for any visible text link containing "Google"
        for frame in page.frames:
            els = await frame.query_selector_all("a, button")
            for el in els:
                txt = (await el.inner_text()).strip().lower()
                if "google" in txt:
                    try:
                        async with page.expect_popup(timeout=8_000) as popup_info:
                            await el.click()
                        google_page = await popup_info.value
                    except PWTimeout:
                        google_page = page
                    break
            if google_page:
                break

    if google_page is None:
        logger.warning("Could not find Google sign-in button.")
        return

    await google_page.wait_for_load_state("domcontentloaded")
    logger.info("Google page: %s", google_page.url)

    # --- Enter email ---
    try:
        await google_page.wait_for_selector("input[type=email]", timeout=15_000)
        await google_page.fill("input[type=email]", GOOGLE_EMAIL)
        await google_page.press("input[type=email]", "Enter")
        logger.info("Email entered.")
    except PWTimeout:
        logger.warning("Email input not found.")
        return

    # --- Enter password ---
    try:
        await google_page.wait_for_selector("input[type=password]", timeout=15_000)
        await asyncio.sleep(1)
        await google_page.fill("input[type=password]", GOOGLE_PASSWORD)
        await google_page.press("input[type=password]", "Enter")
        logger.info("Password entered.")
    except PWTimeout:
        logger.warning("Password input not found.")
        return

    # --- Wait for redirect back to Indeed ---
    # The Google popup closes automatically after OAuth completes, so we
    # catch the TargetClosedError and treat it as a successful redirect.
    logger.info("Waiting for redirect back to Indeed (up to 90s)...")
    try:
        await google_page.wait_for_url("*indeed.com*", timeout=90_000)
        logger.info("Back on Indeed - login complete.")
    except PWTimeout:
        logger.warning("Did not redirect to Indeed within 90s.")
    except Exception as exc:
        if "closed" in str(exc).lower() or "target" in str(exc).lower():
            logger.info("Popup closed after OAuth redirect - login complete.")
        else:
            logger.warning("Unexpected error waiting for redirect: %s", exc)

    await asyncio.sleep(3)


async def ensure_logged_in(context: BrowserContext) -> None:
    """
    Open Indeed home page, sign in with Google if needed,
    then persist cookies to auth_state.json for future runs.
    """
    page = await context.new_page()
    await page.goto(INDEED_BASE, wait_until="domcontentloaded", timeout=30_000)
    await asyncio.sleep(3)

    url = page.url
    logger.info("Indeed landing URL: %s", url)

    needs_login = (
        "sign" in url.lower()
        or "login" in url.lower()
        or await page.query_selector("input[name=email][type=email]") is not None
    )

    if needs_login:
        logger.info("Login required - starting Google OAuth flow.")
        await _sign_in_google(page)
        # After the Google popup closes, wait for the original page to finish its redirect
        try:
            await page.wait_for_url("*indeed.com*", timeout=15_000)
        except Exception:
            pass
        await asyncio.sleep(3)
        await context.storage_state(path=AUTH_STATE_PATH)
        logger.info("Auth state saved to %s", AUTH_STATE_PATH)
    else:
        logger.info("Already authenticated.")

    await page.close()


async def _parse_job_cards(page: Page, field_label: str) -> List[Job]:
    """Extract all job cards from the current search result page."""
    jobs: List[Job] = []
    now = datetime.utcnow().isoformat()

    CARD_SELECTORS = [
        "div.job_seen_beacon",
        "td.resultContent",
        "div[data-testid='slider_item']",
        "li[class*='css-'] div[class*='job']",
    ]

    cards = []
    for sel in CARD_SELECTORS:
        try:
            logger.debug("  Trying card selector: %s", sel)
            await page.wait_for_selector(sel, timeout=12_000)
            cards = await page.query_selector_all(sel)
            if cards:
                logger.info("  Selector '%s' matched %d cards", sel, len(cards))
                break
        except PWTimeout:
            logger.debug("  Selector '%s' timed out.", sel)
            continue

    if not cards:
        logger.warning("No job cards matched any selector on this page (url=%s).", page.url)
        return jobs

    logger.debug("Parsing %d job cards...", len(cards))

    for card in cards:
        try:
            title_el = (
                await card.query_selector("h2.jobTitle span[title]")
                or await card.query_selector("h2.jobTitle span")
                or await card.query_selector("[data-testid='jobTitle']")
                or await card.query_selector("h2 a span")
            )
            title = (await title_el.inner_text()).strip() if title_el else "Unknown Title"

            company_el = (
                await card.query_selector("[data-testid='company-name']")
                or await card.query_selector("span.companyName")
            )
            company = (await company_el.inner_text()).strip() if company_el else "Unknown Company"

            # Skip companies on the blocklist (case-insensitive substring match)
            company_lower = company.lower()
            if any(blocked.lower() in company_lower for blocked in BLOCKED_COMPANIES):
                logger.debug("  Skipping blocked company: %s", company)
                continue

            loc_el = (
                await card.query_selector("[data-testid='text-location']")
                or await card.query_selector("div.companyLocation")
            )
            location = (await loc_el.inner_text()).strip() if loc_el else "Unknown Location"

            link_el = (
                await card.query_selector("h2.jobTitle a")
                or await card.query_selector("h2 a")
                or await card.query_selector("a[data-jk]")
            )
            href = await link_el.get_attribute("href") if link_el else None
            url = urljoin(INDEED_BASE, href) if href else INDEED_BASE

            date_el = (
                await card.query_selector("span[data-testid='myJobsStateDate']")
                or await card.query_selector("span.date")
            )
            date_posted = (await date_el.inner_text()).strip() if date_el else ""

            # Click the card to load the right-side detail panel, then read the
            # full job description from #jobDescriptionText.  Only click for
            # jobs not already in the DB — avoids unnecessary clicks that
            # increase bot-detection risk.  Falls back to the inline snippet.
            description = ""
            if link_el and not url_exists(url):
                try:
                    # Scroll the card into view and hover before clicking —
                    # mimics the mouse path a human user would take.
                    await link_el.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                    await link_el.hover()
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    await link_el.click()
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    await page.wait_for_selector(
                        "#jobDescriptionText", state="visible", timeout=8_000
                    )
                    detail_el = await page.query_selector("#jobDescriptionText")
                    if detail_el:
                        description = (await detail_el.inner_text()).strip()
                except Exception as exc:
                    logger.debug(
                        "Detail panel did not load for '%s': %s — falling back to snippet",
                        title, exc,
                    )
            if not description:
                snippet_el = (
                    await card.query_selector("div.job-snippet")
                    or await card.query_selector("[class*='snippet']")
                )
                description = (await snippet_el.inner_text()).strip() if snippet_el else ""

            # Easy Apply: Indeed hosts the application itself (no external redirect)
            easy_apply = bool(
                await card.query_selector("[data-testid='indeedApplyButton']")
                or await card.query_selector("button[aria-label*='Apply now']")
                or await card.query_selector("span.iaLabel")
                or await card.query_selector("[class*='indeedApply']")
            )

            jobs.append(Job(
                title=title, company=company, location=location,
                description=description, url=url, date_posted=date_posted,
                field_label=field_label, scraped_at=now, easy_apply=easy_apply,
            ))
            logger.debug("  Parsed: [%s] %s @ %s (easy_apply=%s)",
                         field_label, title, company, easy_apply)

        except Exception as exc:
            logger.warning("Failed to parse job card: %s", exc)
            continue

    return jobs


async def scrape_field(
    context: BrowserContext,
    query: str,
    location: str,
    field_label: str,
) -> List[Job]:
    """
    Scrape Indeed for one search query.
    Stops early when MAX_NEW_JOBS_PER_FIELD unseen jobs are found,
    or when MAX_PAGES_PER_FIELD pages are exhausted.
    Jobs whose URL already exists in the DB are skipped and do NOT
    count toward the new-job target.
    """
    new_jobs: List[Job] = []   # only jobs not already in the DB
    page = await context.new_page()
    logger.info("scrape_field START  query=%r  location=%r  field=%r", query, location, field_label)

    try:
        for page_num in range(MAX_PAGES_PER_FIELD):
            start = page_num * 15
            url = _build_url(query, location, start)
            logger.info("[%s | %s] Page %d/%d  start=%d", field_label, location, page_num + 1, MAX_PAGES_PER_FIELD, start)

            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    logger.debug("  Navigating to: %s  (attempt %d/%d)", url, attempt, MAX_RETRIES)
                    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    logger.debug("  Page loaded. Final URL: %s", page.url)
                    await _random_delay()
                    success = True
                    break
                except Exception as exc:
                    logger.warning("  Attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
                    await asyncio.sleep(2 ** attempt)

            if not success:
                logger.error("  All %d attempts failed for page %d — skipping.", MAX_RETRIES, page_num + 1)
                continue

            page_jobs = await _parse_job_cards(page, field_label)
            logger.info("  Page %d: %d jobs parsed.", page_num + 1, len(page_jobs))

            if not page_jobs:
                logger.info("  No jobs on page %d — stopping pagination.", page_num + 1)
                break

            page_new = 0
            for job in page_jobs:
                if url_exists(job.url):
                    logger.debug("  Skipping duplicate URL: %s", job.url)
                else:
                    new_jobs.append(job)
                    page_new += 1

            logger.info("  Page %d: %d new (unseen) jobs. Running total: %d/%d.",
                        page_num + 1, page_new, len(new_jobs), MAX_NEW_JOBS_PER_FIELD)

            if len(new_jobs) >= MAX_NEW_JOBS_PER_FIELD:
                logger.info("  Reached %d new jobs — stopping early.", MAX_NEW_JOBS_PER_FIELD)
                break

    finally:
        await page.close()

    logger.info("scrape_field END  query=%r  location=%r  new_jobs=%d", query, location, len(new_jobs))
    return new_jobs
