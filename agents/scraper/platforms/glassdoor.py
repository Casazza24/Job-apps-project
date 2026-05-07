"""Glassdoor job scraper using Playwright."""
import asyncio
import random
import re
from typing import List, Dict, Any
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from agents.scraper.platforms.base import BaseScraper
from shared.keywords import SEARCH_KEYWORDS
from shared.logger import get_logger

logger = get_logger("scraper.glassdoor")

BASE_URL = "https://www.glassdoor.com/Job/jobs.htm?suggestCount=0&suggestChosen=false&clickSource=searchBtn&typedKeyword={keyword}&sc.keyword={keyword}&locT=N&fromAge=7"


class GlassdoorScraper(BaseScraper):

    async def login(self, page) -> None:
        await page.goto("https://www.glassdoor.com/profile/login_input.htm", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        try:
            await page.fill("input[name='username'], #userEmail", self.email)
            await page.fill("input[name='password'], #userPassword", self.password)
            await page.click("button[type=submit], #signInBtn")
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            logger.warning("Glassdoor login issue", extra={"error": str(e)})
        logger.info("Glassdoor login attempted")

    async def scrape(self) -> List[Dict[str, Any]]:
        if not self.email or not self.password:
            logger.warning("Glassdoor credentials not set, skipping")
            return []

        jobs = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
                            logger.warning("CAPTCHA on Glassdoor — pausing", extra={"keyword": keyword})
                            # CAPTCHA on Glassdoor is expected; skip and notify via status
                            continue

                        # Close sign-in modal if present
                        try:
                            close_btn = await page.query_selector("button[alt='Close'], .modal_closeIcon")
                            if close_btn:
                                await close_btn.click()
                                await page.wait_for_timeout(500)
                        except Exception:
                            pass

                        cards = await page.query_selector_all("li.react-job-listing, [data-test='jobListing']")
                        for card in cards[:15]:
                            try:
                                job = await self._extract_job(card)
                                if job:
                                    jobs.append(job)
                            except Exception:
                                pass

                        await page.wait_for_timeout(random.randint(2000, 4000))
                    except PlaywrightTimeout:
                        logger.warning("Glassdoor timeout", extra={"keyword": keyword})
                    except Exception as e:
                        logger.error("Glassdoor error", extra={"keyword": keyword, "error": str(e)})
            finally:
                await browser.close()

        logger.info("Glassdoor scrape complete", extra={"jobs_found": len(jobs)})
        return jobs

    async def _extract_job(self, card) -> Dict[str, Any]:
        title_el = await card.query_selector("[data-test='job-title'], .job-title, a.jobTitle")
        company_el = await card.query_selector("[data-test='employer-name'], .employer-name")
        location_el = await card.query_selector("[data-test='emp-location'], .location")
        salary_el = await card.query_selector("[data-test='detailSalary'], .salary-estimate")

        title = (await title_el.inner_text()).strip() if title_el else ""
        company = (await company_el.inner_text()).strip() if company_el else ""
        location = (await location_el.inner_text()).strip() if location_el else ""
        salary = (await salary_el.inner_text()).strip() if salary_el else None
        href = await title_el.get_attribute("href") if title_el else ""

        if not title or not href:
            return None
        if not href.startswith("http"):
            href = "https://www.glassdoor.com" + href

        id_match = re.search(r"jobListingId=(\d+)|/job-listing/[^/]+-JV_IC\d+_KO\d+,\d+_KE(\d+)", href)
        external_id = f"glassdoor_{id_match.group(1) or abs(hash(href))}" if id_match else f"glassdoor_{abs(hash(href))}"

        return {
            "external_id": external_id,
            "platform": "glassdoor",
            "title": title,
            "company": company,
            "location": location,
            "salary_range": salary,
            "url": href,
            "description": "",
            "is_workday": False,
            "workday_url": None,
        }
