"""
Glassdoor application submitter.
Note: Glassdoor typically redirects to the employer's site.
This submitter handles the redirect and fills the external form.
"""
import asyncio
import random
from typing import Dict, Any
from playwright.async_api import async_playwright
from agents.submitter.platforms.base_submitter import BaseSubmitter
from agents.submitter.form_filler import fill_common_fields, upload_resume, fill_text_field
from shared.config import get_secret
from shared.logger import get_logger

logger = get_logger("submitter.glassdoor")


class GlassdoorSubmitter(BaseSubmitter):

    async def submit(self, application: Dict[str, Any]) -> None:
        job_url = application.get("job_url", "")
        resume_bytes = self._get_resume_bytes(application)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                # Login to Glassdoor
                await page.goto("https://www.glassdoor.com/profile/login_input.htm", wait_until="domcontentloaded")
                await fill_text_field(page, "input[name='username'], #userEmail", get_secret("GLASSDOOR_EMAIL"))
                await fill_text_field(page, "input[name='password'], #userPassword", get_secret("GLASSDOOR_PASSWORD"))
                await page.click("button[type=submit], #signInBtn")
                await page.wait_for_load_state("networkidle", timeout=15000)

                # Navigate to the job listing
                await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                # Close modal if present
                try:
                    close_btn = await page.query_selector("button[alt='Close'], .modal_closeIcon")
                    if close_btn:
                        await close_btn.click()
                        await page.wait_for_timeout(500)
                except Exception:
                    pass

                # Click apply — usually redirects to external site
                apply_btn = await page.query_selector("button[data-test='applyButton'], a[data-test='applyButton'], button:has-text('Apply')")
                if not apply_btn:
                    raise Exception("No apply button on Glassdoor job page")
                await apply_btn.click()
                await page.wait_for_timeout(3000)

                # We may now be on an external company site
                logger.info("Redirected after Glassdoor apply click", extra={"current_url": page.url})

                # Try to fill the external form
                await fill_common_fields(page, self.config, application)
                if resume_bytes:
                    await upload_resume(page, resume_bytes)

                # Try to submit
                for _ in range(5):
                    next_btn = await page.query_selector("button:has-text('Submit'), button:has-text('Apply'), button:has-text('Next'), button[type='submit']")
                    if not next_btn:
                        break
                    text = (await next_btn.inner_text()).lower()
                    await next_btn.click()
                    await page.wait_for_timeout(random.randint(1500, 2500))
                    if "submit" in text or "apply" in text:
                        break

                logger.info("Glassdoor/external application submitted", extra={"final_url": page.url})
            finally:
                await browser.close()
