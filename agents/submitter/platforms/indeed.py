"""Indeed application submitter."""
import asyncio
import random
from typing import Dict, Any
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from agents.submitter.platforms.base_submitter import BaseSubmitter
from agents.submitter.form_filler import fill_common_fields, upload_resume, fill_text_field
from shared.config import get_secret
from shared.logger import get_logger

logger = get_logger("submitter.indeed")


class IndeedSubmitter(BaseSubmitter):

    async def submit(self, application: Dict[str, Any]) -> None:
        job_url = application.get("job_url", "")
        resume_bytes = self._get_resume_bytes(application)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                # Login to Indeed
                await page.goto("https://secure.indeed.com/account/login", wait_until="domcontentloaded")
                await fill_text_field(page, "#ifl-InputFormField-3, input[type='email']", get_secret("INDEED_EMAIL"))
                await page.click("button[type=submit]")
                await page.wait_for_timeout(2000)
                await fill_text_field(page, "input[type='password']", get_secret("INDEED_PASSWORD"))
                await page.click("button[type=submit]")
                await page.wait_for_load_state("networkidle", timeout=15000)

                # Navigate to job
                await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                # Click Apply
                apply_btn = await page.query_selector("button#indeedApplyButton, a[data-tn-element='applyOnCompanySite'], button:has-text('Apply now')")
                if not apply_btn:
                    raise Exception("No apply button found on Indeed job page")
                await apply_btn.click()
                await page.wait_for_timeout(2000)

                # Fill form fields
                await fill_common_fields(page, self.config, application)
                if resume_bytes:
                    await upload_resume(page, resume_bytes)

                # Multi-step navigation
                for _ in range(6):
                    await fill_common_fields(page, self.config, application)
                    next_btn = await page.query_selector("button:has-text('Continue'), button:has-text('Next'), button:has-text('Submit')")
                    if not next_btn:
                        break
                    text = (await next_btn.inner_text()).lower()
                    await next_btn.click()
                    await page.wait_for_timeout(random.randint(1500, 2500))
                    if "submit" in text:
                        break

                logger.info("Indeed application submitted", extra={"job_url": job_url})
            finally:
                await browser.close()
