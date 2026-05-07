"""
Workday job scraper.
Workday boards share a consistent URL pattern: *.wd5.myworkdayjobs.com
We detect Workday URLs from Indeed/Glassdoor redirects and also scrape known Workday boards.
"""
import asyncio
import re
import random
import httpx
from typing import List, Dict, Any

from agents.scraper.platforms.base import BaseScraper
from shared.keywords import SEARCH_KEYWORDS
from shared.logger import get_logger

logger = get_logger("scraper.workday")

WORKDAY_URL_PATTERN = re.compile(r"https?://([a-z0-9\-]+)\.wd\d+\.myworkdayjobs\.com", re.IGNORECASE)

# Known Workday job boards for target companies
WORKDAY_BOARDS = [
    "https://amazon.jobs/en/search?base_query=data+intern&loc_query=&job_type=intern",
    "https://microsoft.wd5.myworkdayjobs.com/en-US/External",
    "https://nike.wd1.myworkdayjobs.com/en-US/NikeCareerSite",
    "https://target.wd5.myworkdayjobs.com/en-US/TGT_Careers",
    "https://walmart.wd5.myworkdayjobs.com/WalmartExternal",
    "https://capitalone.wd1.myworkdayjobs.com/Capital_One",
    "https://paypal.wd1.myworkdayjobs.com/jobsatpaypal",
    "https://uber.wd5.myworkdayjobs.com/ATG_External_Careers",
    "https://twitter.wd5.myworkdayjobs.com/en-US/Twitter",
    "https://bloomberg.wd1.myworkdayjobs.com/en-US/Bloomberglp_External",
]


class WorkdayScraper(BaseScraper):

    async def login(self, page) -> None:
        # Workday scraping uses public job listing pages
        pass

    async def scrape(self) -> List[Dict[str, Any]]:
        jobs = []
        keywords_lower = [k.lower() for k in SEARCH_KEYWORDS]

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for board_url in WORKDAY_BOARDS:
                try:
                    # Use Workday's JSON API if available
                    match = WORKDAY_URL_PATTERN.match(board_url)
                    if match:
                        company = match.group(1)
                        # Try Workday v1 API
                        api_url = f"https://{company}.wd5.myworkdayjobs.com/wday/cxs/{company}/External/jobs"
                        payload = {
                            "appliedFacets": {},
                            "limit": 20,
                            "offset": 0,
                            "searchText": "intern data engineer",
                        }
                        resp = await client.post(api_url, json=payload,
                                                  headers={"Content-Type": "application/json"})
                        if resp.status_code == 200:
                            data = resp.json()
                            for item in data.get("jobPostings", []):
                                title = item.get("title", "")
                                title_lower = title.lower()
                                if not any(kw in title_lower for kw in ["intern", "data", "engineer", "analyst", "ml"]):
                                    continue
                                ext_path = item.get("externalPath", "")
                                job_url = f"https://{company}.wd5.myworkdayjobs.com{ext_path}"
                                jobs.append({
                                    "external_id": f"workday_{company}_{item.get('bulletFields', [''])[0][:20]}_{abs(hash(job_url))}",
                                    "platform": "workday",
                                    "title": title,
                                    "company": company.title(),
                                    "location": item.get("locationsText", ""),
                                    "salary_range": None,
                                    "url": job_url,
                                    "description": item.get("jobDescription", "")[:3000],
                                    "is_workday": True,
                                    "workday_url": job_url,
                                })

                    await asyncio.sleep(random.uniform(1, 2))
                except Exception as e:
                    logger.debug("Workday board error", extra={"url": board_url, "error": str(e)})

        logger.info("Workday scrape complete", extra={"jobs_found": len(jobs)})
        return jobs


def extract_workday_domain(url: str) -> str:
    """Extract the Workday subdomain from a URL."""
    match = WORKDAY_URL_PATTERN.search(url)
    if match:
        return match.group(0).split("://")[1]
    return url.split("/")[2] if "://" in url else url
