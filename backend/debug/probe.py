# debug/probe.py - Dev tool for probing Playwright / Indeed card structure
#
# Run from the backend/ directory:
#   python debug/probe.py

import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import asyncio
from playwright.async_api import async_playwright
from config import AUTH_STATE_PATH


async def check():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context(
            storage_state=AUTH_STATE_PATH,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()
        await page.goto("https://www.indeed.com/jobs?q=entry+level+software+engineer&l=20878&radius=100", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        cards = await page.query_selector_all("div.job_seen_beacon")
        print(f"Cards found: {len(cards)}")
        if not cards:
            await browser.close()
            return

        # Check easy apply indicator on the card itself (before click)
        for i, card in enumerate(cards[:5]):
            html = await card.inner_html()
            has_ia = "iaLabel" in html or "indeedApply" in html.lower() or "easy apply" in html.lower()
            print(f"  Card {i}: easy_apply_hint={has_ia}")

        # Click first card and probe detail panel
        await cards[0].click()
        await asyncio.sleep(2)

        selectors = [
            "span.iaLabel",
            "[data-testid='indeedApplyButton']",
            "button[aria-label*='Apply']",
            "[class*='indeedApply']",
            "[data-indeed-apply]",
            "span[class*='apply' i]",
            "button:has-text('Apply')",
        ]
        for sel in selectors:
            els = await page.query_selector_all(sel)
            if els:
                txt = await els[0].inner_text()
                print(f"  FOUND {len(els)}x {sel!r} -> text={txt[:40]!r}")

        # Dump all data-testid from right panel
        panel = await page.query_selector("#mosaic-vjHeaderWarpContainer, .jobsearch-RightPane, [class*=RightPane]")
        if panel:
            nodes = await panel.query_selector_all("[data-testid]")
            ids = set()
            for n in nodes[:40]:
                t = await n.get_attribute("data-testid")
                if t:
                    ids.add(t)
            print("Panel data-testids:", sorted(ids))

        await asyncio.sleep(3)
        await browser.close()


asyncio.run(check())
