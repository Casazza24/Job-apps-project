"""Handshake job scraper using Playwright — focused on internship/entry-level roles."""
import asyncio
import random
from typing import List, Dict, Any
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from agents.scraper.platforms.base import BaseScraper
from shared.keywords import SEARCH_KEYWORDS
from shared.logger import get_logger

logger = get_logger("scraper.handshake")

BASE_URL = "https://app.joinhandshake.com/postings?page=1&per_page=25&sort_direction=desc&sort_column=created_datetime&query={keyword}"


class HandshakeScraper(BaseScraper):

    async def login(self, page) -> None:
        await page.goto("https://app.joinhandshake.com/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        try:
            await page.fill("input[name='email'], input[type='email']", self.email)
            await page.click("button[type=submit], input[type=submit]")
            await page.wait_for_timeout(1500)
            await page.fill("input[name='password'], input[type='password']", self.password)
            await page.click("button[type=submit], input[type=submit]")
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception as e:
            logger.warning("Handshake login issue", extra={"error": str(e)})
        logger.info("Handshake login attempted")

    async def scrape(self) -> List[Dict[str, Any]]:
        if not self.email or not self.password:
            logger.warning("Handshake credentials not set, skipping")
            return []

        jobs = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await self.login(page)
                intern_keywords = [k for k in SEARCH_KEYWORDS if "intern" in k.lower()][:6]
                for keyword in intern_keywords:
                    try:
                        url = BASE_URL.format(keyword=quote_plus(keyword))
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(random.randint(2000, 3500))

                        content = await page.content()
                        if self._detect_captcha(content):
                            logger.warning("CAPTCHA on Handshake")
                            continue

                        cards = await page.query_selector_all("[data-hook='posting-card'], .posting-card, article")
                        for card in cards[:15]:
                            try:
                                job = await self._extract_job(card)
                                if job:
                                    jobs.append(job)
                            except Exception:
                                pass

                        await page.wait_for_timeout(random.randint(2000, 4000))
                    except PlaywrightTimeout:
                        logger.warning("Handshake timeout", extra={"keyword": keyword})
                    except Exception as e:
                        logger.error("Handshake error", extra={"keyword": keyword, "error": str(e)})
            finally:
                await browser.close()

        logger.info("Handshake scrape complete", extra={"jobs_found": len(jobs)})
        return jobs

    async def _extract_job(self, card) -> Dict[str, Any]:
        title_el = await card.query_selector("h3, [data-hook='posting-name'], .posting-name")
        company_el = await card.query_selector("[data-hook='employer-name'], .employer-name")
        location_el = await card.query_selector("[data-hook='posting-location'], .location")
        link_el = await card.query_selector("a[href*='/postings/']")

        title = (await title_el.inner_text()).strip() if title_el else ""
        company = (await company_el.inner_text()).strip() if company_el else ""
        location = (await location_el.inner_text()).strip() if location_el else ""
        href = await link_el.get_attribute("href") if link_el else ""

        if not title or not href:
            return None

        if not href.startswith("http"):
            href = "https://app.joinhandshake.com" + href

        import re
        id_match = re.search(r"/postings/(\d+)", href)
        external_id = f"handshake_{id_match.group(1)}" if id_match else f"handshake_{abs(hash(href))}"

        return {
            "external_id": external_id,
            "platform": "handshake",
            "title": title,
            "company": company,
            "location": location,
            "salary_range": None,
            "url": href,
            "description": "",
            "is_workday": False,
            "workday_url": None,
        }
