"""
Workday application submitter.
Handles auto-register per employer domain using Gmail alias trick.
Stores credentials in DB + GCP Secret Manager.
"""
import asyncio
import random
import re
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from agents.submitter.platforms.base_submitter import BaseSubmitter
from agents.submitter.form_filler import fill_common_fields, upload_resume, fill_text_field, generate_secure_password
from shared.db import get_workday_account, save_workday_account
from shared.gcp import create_secret_in_manager
from shared.config import get_secret
from shared.logger import get_logger

logger = get_logger("submitter.workday")

WORKDAY_DOMAIN_RE = re.compile(r"https?://([a-z0-9\-]+\.wd\d+\.myworkdayjobs\.com)", re.IGNORECASE)


def extract_workday_domain(url: str) -> str:
    match = WORKDAY_DOMAIN_RE.search(url)
    return match.group(1) if match else url.split("/")[2]


class WorkdaySubmitter(BaseSubmitter):

    async def submit(self, application: Dict[str, Any]) -> None:
        job_url = application.get("workday_url") or application.get("job_url", "")
        resume_bytes = self._get_resume_bytes(application)
        domain = extract_workday_domain(job_url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(2000)

                account = get_workday_account(domain)

                if account:
                    await self._login(page, account["email"], get_secret(account["password_ref"]))
                else:
                    account_data = await self._register(page, domain)
                    account = account_data

                # Click Apply
                apply_btn = await page.query_selector("a[data-automation-id='applyNowButton'], button:has-text('Apply')")
                if apply_btn:
                    await apply_btn.click()
                    await page.wait_for_timeout(2000)

                # Multi-step Workday form
                for step in range(10):
                    await fill_common_fields(page, self.config, application)
                    if resume_bytes:
                        await upload_resume(page, resume_bytes)

                    cover_letter = application.get("cover_letter_text", "")
                    if cover_letter:
                        await fill_text_field(page, "textarea[data-automation-id*='coverLetter' i]", cover_letter)

                    # Try Next / Submit
                    next_btn = await page.query_selector(
                        "button[data-automation-id='bottom-navigation-next-button'], "
                        "button[data-automation-id='bottom-navigation-forward-button'], "
                        "button:has-text('Next'), button:has-text('Submit')"
                    )
                    if not next_btn:
                        break
                    label = await next_btn.get_attribute("data-automation-id") or await next_btn.inner_text()
                    await next_btn.click()
                    await page.wait_for_timeout(random.randint(2000, 3500))
                    if "submit" in label.lower():
                        break

                logger.info("Workday application submitted", extra={"domain": domain, "job_url": job_url})
            finally:
                await browser.close()

    async def _login(self, page, email: str, password: str) -> None:
        try:
            sign_in = await page.query_selector("a:has-text('Sign In'), button:has-text('Sign In')")
            if sign_in:
                await sign_in.click()
                await page.wait_for_timeout(1500)
            await fill_text_field(page, "input[type='email'], input[data-automation-id='email']", email)
            await fill_text_field(page, "input[type='password']", password)
            await page.click("button[type='submit']")
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning("Workday login issue", extra={"error": str(e)})

    async def _register(self, page, domain: str) -> dict:
        """Register a new Workday account using Gmail alias trick."""
        base_email = self.config.CANDIDATE_EMAIL
        alias_tag = domain.split(".")[0]
        if "@" in base_email:
            local, at_domain = base_email.split("@", 1)
            email_alias = f"{local}+{alias_tag}@{at_domain}"
        else:
            email_alias = base_email

        password = generate_secure_password()

        try:
            create_btn = await page.query_selector("a:has-text('Create Account'), button:has-text('Create Account')")
            if create_btn:
                await create_btn.click()
                await page.wait_for_timeout(1500)

            await fill_text_field(page, "input[data-automation-id='email'], input[name='email']", email_alias)
            await fill_text_field(page, "input[type='password']", password)
            await fill_text_field(page, "input[data-automation-id='firstName'], input[name='firstName']", self.config.CANDIDATE_FIRST_NAME)
            await fill_text_field(page, "input[data-automation-id='lastName'], input[name='lastName']", self.config.CANDIDATE_LAST_NAME)
            await page.click("button[type='submit']")
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning("Workday registration issue", extra={"error": str(e)})

        # Save credentials
        secret_name = f"workday_{domain.replace('.', '_').replace('-', '_')}"
        if self.config.GCP_PROJECT_ID and self.config.ENV != "local":
            create_secret_in_manager(self.config.GCP_PROJECT_ID, secret_name, password)
        save_workday_account(domain, email_alias, secret_name)

        logger.info("Workday account created", extra={"domain": domain, "email": email_alias})
        return {"email": email_alias, "password_ref": secret_name}
