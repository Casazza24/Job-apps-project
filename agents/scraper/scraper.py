"""
Main Scraper Agent entrypoint.
Iterates all enabled platforms, scrapes jobs, deduplicates, inserts into DB.
Then triggers the orchestrator.
"""
import asyncio
import random
import time
from shared.config import get_config
from shared.db import insert_job
from shared.logger import get_logger
from shared.platforms_registry import get_enabled_scrapers
from agents.scraper.deduplicator import Deduplicator

logger = get_logger("scraper")


async def run_scraper() -> None:
    config = get_config()
    dedup = Deduplicator()
    scrapers_cfg = get_enabled_scrapers()
    total_inserted = 0

    for platform_name, cfg in scrapers_cfg.items():
        ScraperClass = cfg["scraper"]
        credential_prefix = cfg["credential_prefix"]
        logger.info("Starting scraper", extra={"platform": platform_name})

        try:
            scraper = ScraperClass(db=None, config=config, credential_prefix=credential_prefix)
            jobs = await scraper.scrape()
            new_jobs = dedup.filter_new(jobs)
            logger.info("Scraped jobs", extra={
                "platform": platform_name,
                "total": len(jobs),
                "new": len(new_jobs),
            })

            for job in new_jobs:
                job.setdefault("is_workday", False)
                job.setdefault("workday_url", None)
                job.setdefault("salary_range", None)
                job.setdefault("location", None)
                job.setdefault("description", "")
                try:
                    inserted_id = insert_job(job)
                    if inserted_id:
                        total_inserted += 1
                except Exception as e:
                    logger.error("Failed to insert job", extra={"error": str(e), "job": job.get("title")})

            # Polite delay between platforms
            await asyncio.sleep(random.uniform(2, 5))

        except Exception as e:
            logger.error("Scraper failed for platform", extra={"platform": platform_name, "error": str(e)})

    logger.info("Scraping complete", extra={"total_inserted": total_inserted})

    # Trigger orchestrator after scraping
    try:
        from agents.orchestrator.orchestrator import run_orchestrator
        run_orchestrator()
    except Exception as e:
        logger.error("Orchestrator failed after scraping", extra={"error": str(e)})


if __name__ == "__main__":
    asyncio.run(run_scraper())
