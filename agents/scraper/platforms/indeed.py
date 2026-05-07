"""Indeed job scraper using Playwright."""
import asyncio
import random
import re
from typing import List, Dict, Any
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from agents.scraper.platforms.base import BaseScraper
from shared.keywords import SEARCH_KEYWORDS
from shared.logger import get_logger

logger = get_logger("scraper.indeed")

BASE_URL = "https://www.indeed.com/jobs?q={keyword}&fromage=7&sort=date"
WORKDAY_PATTERN = re.compile(r"https?://[a-z0-9\-]+\.wd\d+\.myworkdayjobs\.com", re.IGNORECASE)


class IndeedScraper(BaseScraper):

    async def login(self, page) -> None:
        await page.goto("https://secure.indeed.com/account/login", wait_until="domcontentloaded")
        await page.fill("#ifl-InputFormField-3", self.email)
        await page.click("button[type=submit]")
        await page.wait_for_timeout(2000)
        try:
            await page.fill("#ifl-InputFormField-7", self.password)
            await page.click("button[type=submit]")
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        logger.info("Indeed login attempted")

    async def scrape(self) -> List[Dict[str, Any]]:
        if not self.email or not self.password:
            logger.warning("Indeed credentials not set, skipping")
            return []

        jobs = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()
            try:
                await self.login(page)
                for keyword in SEARCH_KEYWORDS[:8]:
                    try:
                        url = BASE_URL.format(keyword=quote_plus(keyword))
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(random.randint(2000, 3500))

                        content = await page.content()
                        if self._detect_captcha(content):
                            logger.warning("CAPTCHA on Indeed", extra={"keyword": keyword})
                            continue

                        cards = await page.query_selector_all(".job_seen_beacon, .tapItem")
                        for card in cards[:15]:
                            try:
                                job = await self._extract_job(card)
                                if job:
                                    jobs.append(job)
                            except Exception:
                                pass

                        await page.wait_for_timeout(random.randint(2000, 4000))
                    except PlaywrightTimeout:
                        logger.warning("Indeed timeout", extra={"keyword": keyword})
                    except Exception as e:
                        logger.error("Indeed error", extra={"keyword": keyword, "error": str(e)})
            finally:
                await browser.close()

        logger.info("Indeed scrape complete", extra={"jobs_found": len(jobs)})
        return jobs

    async def _extract_job(self, card) -> Dict[str, Any]:
        title_el = await card.query_selector("[class*='jobTitle'] a, h2.jobTitle a")
        company_el = await card.query_selector("[data-testid='company-name'], .companyName")
        location_el = await card.query_selector("[data-testid='text-location'], .companyLocation")
        salary_el = await card.query_selector("[data-testid='attribute_snippet_testid']")

        title = (await title_el.inner_text()).strip() if title_el else ""
        company = (await company_el.inner_text()).strip() if company_el else ""
        location = (await location_el.inner_text()).strip() if location_el else ""
        salary = (await salary_el.inner_text()).strip() if salary_el else None

        href = await title_el.get_attribute("href") if title_el else ""
        if not href:
            return None
        if not href.startswith("http"):
            href = "https://www.indeed.com" + href

        # Extract jk param as external_id
        jk_match = re.search(r"jk=([a-z0-9]+)", href)
        external_id = f"indeed_{jk_match.group(1)}" if jk_match else f"indeed_{abs(hash(href))}"

        # Check for Workday redirect
        is_workday = bool(WORKDAY_PATTERN.search(href))

        return {
            "external_id": external_id,
            "platform": "indeed",
            "title": title,
            "company": company,
            "location": location,
            "salary_range": salary,
            "url": href,
            "description": "",
            "is_workday": is_workday,
            "workday_url": href if is_workday else None,
        }
