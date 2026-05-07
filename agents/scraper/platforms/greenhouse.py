"""
Greenhouse job scraper.
Greenhouse boards use a consistent API: boards.greenhouse.io/COMPANY/jobs.json
We scrape via the JSON API rather than the rendered page for reliability.
"""
import asyncio
import httpx
import random
from typing import List, Dict, Any
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from agents.scraper.platforms.base import BaseScraper
from shared.keywords import SEARCH_KEYWORDS
from shared.logger import get_logger

logger = get_logger("scraper.greenhouse")

# Well-known Greenhouse boards for target companies (expand this list)
GREENHOUSE_COMPANIES = [
    "airbnb", "stripe", "lyft", "doordash", "robinhood",
    "plaid", "figma", "notion", "databricks", "snowflake",
    "scale", "openai", "anthropic", "cohere", "huggingface",
    "palantir", "datadog", "twilio", "sendbird", "benchling",
]


class GreenhouseScraper(BaseScraper):

    async def login(self, page) -> None:
        # Greenhouse boards are public — no login required for scraping
        pass

    async def scrape(self) -> List[Dict[str, Any]]:
        jobs = []
        keywords_lower = {k.lower() for k in SEARCH_KEYWORDS}

        async with httpx.AsyncClient(timeout=15) as client:
            for company in GREENHOUSE_COMPANIES:
                try:
                    resp = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true")
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for item in data.get("jobs", []):
                        title = item.get("title", "").lower()
                        if not any(kw in title for kw in ["intern", "data", "engineer", "analyst", "ml", "ai", "science"]):
                            continue
                        if "senior" in title or "staff" in title or "principal" in title or "director" in title:
                            continue

                        job_id = str(item.get("id", ""))
                        jobs.append({
                            "external_id": f"greenhouse_{job_id}",
                            "platform": "greenhouse",
                            "title": item.get("title", ""),
                            "company": company.title(),
                            "location": item.get("location", {}).get("name", ""),
                            "salary_range": None,
                            "url": item.get("absolute_url", ""),
                            "description": item.get("content", "")[:3000],
                            "is_workday": False,
                            "workday_url": None,
                        })

                    await asyncio.sleep(random.uniform(0.5, 1.5))
                except Exception as e:
                    logger.debug("Greenhouse API error", extra={"company": company, "error": str(e)})

        logger.info("Greenhouse scrape complete", extra={"jobs_found": len(jobs)})
        return jobs
