"""LinkedIn Easy Apply submitter."""
import asyncio
import random
from typing import Dict, Any
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from agents.submitter.platforms.base_submitter import BaseSubmitter
from agents.submitter.form_filler import fill_common_fields, upload_resume, fill_text_field
from shared.config import get_secret
from shared.logger import get_logger

logger = get_logger("submitter.linkedin")


class LinkedInSubmitter(BaseSubmitter):

    async def submit(self, application: Dict[str, Any]) -> None:
        job_url = application.get("job_url", "")
        resume_bytes = self._get_resume_bytes(application)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                # Login
                await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
                await fill_text_field(page, "#username", get_secret("LINKEDIN_EMAIL"))
                await fill_text_field(page, "#password", get_secret("LINKEDIN_PASSWORD"))
                await page.click("button[type=submit]")
                await page.wait_for_load_state("networkidle", timeout=15000)

                # Navigate to job
                await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                # Click Easy Apply
                easy_apply = await page.query_selector("button.jobs-apply-button, button[aria-label*='Easy Apply']")
                if not easy_apply:
                    raise Exception("No Easy Apply button found on this job")
                await easy_apply.click()
                await page.wait_for_timeout(2000)

                # Fill multi-step form
                for step in range(8):  # LinkedIn Easy Apply can have up to 8 steps
                    await fill_common_fields(page, self.config, application)
                    if resume_bytes:
                        await upload_resume(page, resume_bytes)

                    # Check for cover letter field
                    cover_letter = application.get("cover_letter_text", "")
                    if cover_letter:
                        await fill_text_field(page, "textarea[id*='cover-letter'], textarea[name*='coverLetter']", cover_letter)

                    # Try to click Next or Submit
                    next_btn = await page.query_selector("button[aria-label='Continue to next step'], button[aria-label='Submit application']")
                    if not next_btn:
                        next_btn = await page.query_selector("button:has-text('Next'), button:has-text('Submit'), button:has-text('Review')")
                    if not next_btn:
                        break
                    label = await next_btn.get_attribute("aria-label") or await next_btn.inner_text()
                    await next_btn.click()
                    await page.wait_for_timeout(random.randint(1500, 2500))
                    if "submit" in label.lower():
                        break

                logger.info("LinkedIn Easy Apply submitted", extra={"job_url": job_url})
            finally:
                await browser.close()
