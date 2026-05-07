"""Handshake application submitter."""
import asyncio
import random
from typing import Dict, Any
from playwright.async_api import async_playwright
from agents.submitter.platforms.base_submitter import BaseSubmitter
from agents.submitter.form_filler import fill_common_fields, upload_resume, fill_text_field
from shared.config import get_secret
from shared.logger import get_logger

logger = get_logger("submitter.handshake")


class HandshakeSubmitter(BaseSubmitter):

    async def submit(self, application: Dict[str, Any]) -> None:
        job_url = application.get("job_url", "")
        resume_bytes = self._get_resume_bytes(application)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                # Login
                await page.goto("https://app.joinhandshake.com/login", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                await fill_text_field(page, "input[type='email'], input[name='email']", get_secret("HANDSHAKE_EMAIL"))
                await page.click("button[type=submit]")
                await page.wait_for_timeout(1500)
                await fill_text_field(page, "input[type='password'], input[name='password']", get_secret("HANDSHAKE_PASSWORD"))
                await page.click("button[type=submit]")
                await page.wait_for_load_state("networkidle", timeout=20000)

                # Navigate to job
                await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                # Click Apply
                apply_btn = await page.query_selector("button:has-text('Apply'), a:has-text('Apply Now')")
                if not apply_btn:
                    raise Exception("No apply button found on Handshake job")
                await apply_btn.click()
                await page.wait_for_timeout(2000)

                await fill_common_fields(page, self.config, application)
                if resume_bytes:
                    await upload_resume(page, resume_bytes)

                cover_letter = application.get("cover_letter_text", "")
                if cover_letter:
                    await fill_text_field(page, "textarea[name*='coverLetter'], textarea[id*='cover']", cover_letter)

                submit_btn = await page.query_selector("button:has-text('Submit'), button[type='submit']")
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_timeout(2000)

                logger.info("Handshake application submitted", extra={"job_url": job_url})
            finally:
                await browser.close()
