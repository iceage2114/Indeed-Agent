# scraping/agent.py - Main entry point; orchestrates all searches
#
# Run from the backend/ directory:
#   python scraping/agent.py

import os
import sys

# Ensure the backend root is on the path when running this script directly.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import asyncio
import logging
import random

from playwright.async_api import async_playwright

from config import SEARCH_FIELDS, LOCATIONS, BASE_DIR, AUTH_STATE_PATH, \
    INTER_SEARCH_DELAY_MIN, INTER_SEARCH_DELAY_MAX, \
    INTER_LOCATION_DELAY_MIN, INTER_LOCATION_DELAY_MAX
from scraping.scraper import scrape_field, ensure_logged_in
from db.writer import merge_and_save

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(BASE_DIR, "logs", "agent.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def run_all_searches():
    logger.info("=== Indeed Job Agent starting ===")
    logger.info("Locations: %s", LOCATIONS)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )

        # Load saved auth cookies if they exist (skip login on re-runs)
        ctx_kwargs = dict(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        if os.path.exists(AUTH_STATE_PATH):
            ctx_kwargs["storage_state"] = AUTH_STATE_PATH
            logger.info("Loaded saved auth state from %s", AUTH_STATE_PATH)

        context = await browser.new_context(**ctx_kwargs)

        # Mask navigator.webdriver so JS-level bot checks return undefined
        # (the launch flag removes the Chrome banner; this patches the JS property)
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Sign in once if needed
        await ensure_logged_in(context)

        total_new = 0
        for loc_idx, location in enumerate(LOCATIONS):
            if loc_idx > 0:
                delay = random.uniform(INTER_LOCATION_DELAY_MIN, INTER_LOCATION_DELAY_MAX)
                logger.info("Cooling down %.0fs before next location...", delay)
                await asyncio.sleep(delay)

            logger.info("")
            logger.info("=== Location: %s ===", location)
            for field_idx, field in enumerate(SEARCH_FIELDS):
                if field_idx > 0:
                    delay = random.uniform(INTER_SEARCH_DELAY_MIN, INTER_SEARCH_DELAY_MAX)
                    logger.info("Cooling down %.0fs before next search...", delay)
                    await asyncio.sleep(delay)

                logger.info("")
                logger.info(">>> Searching: '%s' in '%s'", field["label"], location)
                jobs = await scrape_field(
                    context=context,
                    query=field["query"],
                    location=location,
                    field_label=field["label"],
                )
                new_count = merge_and_save(jobs)
                logger.info(">>> Added %d new jobs for field '%s' in '%s'", new_count, field["label"], location)
                total_new += new_count

        await browser.close()

    logger.info("")
    logger.info("=== Done. %d new jobs added across all fields. ===", total_new)


if __name__ == "__main__":
    asyncio.run(run_all_searches())
