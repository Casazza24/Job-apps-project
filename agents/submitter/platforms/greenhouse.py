"""
Greenhouse application submitter.
Greenhouse has a consistent form structure across all companies.
"""
import asyncio
import random
from typing import Dict, Any
from playwright.async_api import async_playwright
from agents.submitter.platforms.base_submitter import BaseSubmitter
from agents.submitter.form_filler import fill_common_fields, upload_resume, fill_text_field
from shared.logger import get_logger

logger = get_logger("submitter.greenhouse")


class GreenhouseSubmitter(BaseSubmitter):

    async def submit(self, application: Dict[str, Any]) -> None:
        job_url = application.get("job_url", "")
        resume_bytes = self._get_resume_bytes(application)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                # Greenhouse job boards are public — no login needed
                await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                # Click Apply
                apply_btn = await page.query_selector("a#btn-apply, a:has-text('Apply for this Job'), button:has-text('Apply')")
                if apply_btn:
                    await apply_btn.click()
                    await page.wait_for_timeout(2000)

                # Greenhouse standard fields
                await fill_text_field(page, "#first_name", self.config.CANDIDATE_FIRST_NAME)
                await fill_text_field(page, "#last_name", self.config.CANDIDATE_LAST_NAME)
                await fill_text_field(page, "#email", self.config.CANDIDATE_EMAIL)
                await fill_text_field(page, "#phone", "")  # Phone is optional

                # LinkedIn / GitHub / portfolio
                await fill_text_field(page, "input[name*='linkedin' i], input[id*='linkedin' i]", self.config.CANDIDATE_LINKEDIN)
                await fill_text_field(page, "input[name*='github' i], input[id*='github' i]", self.config.CANDIDATE_GITHUB)
                await fill_text_field(page, "input[name*='website' i], input[id*='portfolio' i]", self.config.CANDIDATE_PORTFOLIO)

                # Upload resume
                if resume_bytes:
                    await upload_resume(page, resume_bytes)

                # Cover letter
                cover_letter = application.get("cover_letter_text", "")
                if cover_letter:
                    await fill_text_field(page, "textarea#cover_letter, textarea[name*='cover' i]", cover_letter)

                # Submit
                submit_btn = await page.query_selector("input[type='submit'], button[type='submit'], button:has-text('Submit Application')")
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_timeout(3000)
                    logger.info("Greenhouse application submitted", extra={"job_url": job_url})
                else:
                    raise Exception("Could not find Greenhouse submit button")
            finally:
                await browser.close()
