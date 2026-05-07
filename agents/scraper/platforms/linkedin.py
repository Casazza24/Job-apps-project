"""LinkedIn job scraper using Playwright."""
import asyncio
import random
from typing import List, Dict, Any
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from agents.scraper.platforms.base import BaseScraper
from shared.keywords import SEARCH_KEYWORDS
from shared.logger import get_logger

logger = get_logger("scraper.linkedin")

# LinkedIn time filter: r604800 = past 7 days
BASE_URL = "https://www.linkedin.com/jobs/search/?keywords={keyword}&f_TPR=r604800&f_JT=I"


class LinkedInScraper(BaseScraper):

    async def login(self, page) -> None:
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await page.fill("#username", self.email)
        await page.fill("#password", self.password)
        await page.click("button[type=submit]")
        await page.wait_for_load_state("networkidle", timeout=15000)
        if "checkpoint" in page.url or "challenge" in page.url:
            logger.warning("LinkedIn checkpoint/challenge detected")
        logger.info("LinkedIn login complete")

    async def scrape(self) -> List[Dict[str, Any]]:
        if not self.email or not self.password:
            logger.warning("LinkedIn credentials not set, skipping")
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

                for keyword in SEARCH_KEYWORDS[:10]:  # Cap to avoid rate limits
                    try:
                        url = BASE_URL.format(keyword=quote_plus(keyword))
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(random.randint(1500, 3000))

                        content = await page.content()
                        if self._detect_captcha(content):
                            logger.warning("CAPTCHA detected on LinkedIn", extra={"keyword": keyword})
                            continue

                        # Scroll to load more results
                        for _ in range(3):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1000)

                        job_cards = await page.query_selector_all(".jobs-search-results__list-item")
                        for card in job_cards[:15]:
                            try:
                                job = await self._extract_job(card, page)
                                if job:
                                    jobs.append(job)
                            except Exception as e:
                                logger.debug("Failed to extract LinkedIn job card", extra={"error": str(e)})

                        await page.wait_for_timeout(random.randint(2000, 4000))

                    except PlaywrightTimeout:
                        logger.warning("Timeout scraping LinkedIn keyword", extra={"keyword": keyword})
                    except Exception as e:
                        logger.error("Error on LinkedIn keyword", extra={"keyword": keyword, "error": str(e)})

            finally:
                await browser.close()

        logger.info("LinkedIn scrape complete", extra={"jobs_found": len(jobs)})
        return jobs

    async def _extract_job(self, card, page) -> Dict[str, Any]:
        title_el = await card.query_selector(".job-card-list__title, .base-search-card__title")
        company_el = await card.query_selector(".job-card-container__company-name, .base-search-card__subtitle")
        location_el = await card.query_selector(".job-card-container__metadata-item, .job-search-card__location")
        link_el = await card.query_selector("a.job-card-list__title, a.base-card__full-link")

        title = (await title_el.inner_text()).strip() if title_el else ""
        company = (await company_el.inner_text()).strip() if company_el else ""
        location = (await location_el.inner_text()).strip() if location_el else ""
        href = await link_el.get_attribute("href") if link_el else ""

        if not title or not href:
            return None

        # Extract job ID from URL
        import re
        match = re.search(r"/jobs/view/(\d+)", href)
        external_id = f"linkedin_{match.group(1)}" if match else f"linkedin_{abs(hash(href))}"

        # Click to load description
        description = ""
        try:
            await card.click()
            await page.wait_for_timeout(1500)
            desc_el = await page.query_selector(".jobs-description-content__text, .show-more-less-html__markup")
            if desc_el:
                description = (await desc_el.inner_text()).strip()[:3000]
        except Exception:
            pass

        return {
            "external_id": external_id,
            "platform": "linkedin",
            "title": title,
            "company": company,
            "location": location,
            "salary_range": None,
            "url": href.split("?")[0],
            "description": description,
            "is_workday": False,
            "workday_url": None,
        }
