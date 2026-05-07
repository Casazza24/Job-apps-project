"""
Shared Playwright form-filling helpers used by all platform submitters.
"""
import asyncio
import os
import tempfile
import random
from typing import Optional
from shared.logger import get_logger

logger = get_logger("form_filler")


async def fill_text_field(page, selector: str, value: str, timeout: int = 5000) -> bool:
    """Fill a text input field. Returns True on success."""
    try:
        el = await page.wait_for_selector(selector, timeout=timeout)
        await el.triple_click()
        await el.type(value, delay=random.randint(30, 80))
        return True
    except Exception as e:
        logger.debug("Could not fill field", extra={"selector": selector, "error": str(e)})
        return False


async def upload_resume(page, resume_bytes: bytes, filename: str = "resume.pdf") -> bool:
    """
    Upload a resume PDF to a file input field.
    Writes bytes to a temp file, sets it on any file input found.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, prefix="resume_") as tmp:
        tmp.write(resume_bytes)
        tmp_path = tmp.name

    try:
        file_inputs = await page.query_selector_all("input[type='file']")
        for file_input in file_inputs:
            try:
                await file_input.set_input_files(tmp_path)
                logger.info("Resume uploaded")
                return True
            except Exception:
                continue
        logger.warning("No file input found for resume upload")
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


async def fill_common_fields(page, config, application: dict) -> None:
    """
    Fill common application fields: name, email, phone, LinkedIn, GitHub, portfolio.
    Tries multiple common selector patterns.
    """
    field_map = [
        (["input[name*='firstName' i]", "input[name*='first_name' i]", "input[id*='firstName' i]"], config.CANDIDATE_FIRST_NAME),
        (["input[name*='lastName' i]", "input[name*='last_name' i]", "input[id*='lastName' i]"], config.CANDIDATE_LAST_NAME),
        (["input[type='email']", "input[name*='email' i]", "input[id*='email' i]"], config.CANDIDATE_EMAIL),
        (["input[name*='linkedin' i]", "input[id*='linkedin' i]", "input[placeholder*='linkedin' i]"], config.CANDIDATE_LINKEDIN),
        (["input[name*='github' i]", "input[id*='github' i]", "input[placeholder*='github' i]"], config.CANDIDATE_GITHUB),
        (["input[name*='portfolio' i]", "input[name*='website' i]", "input[id*='portfolio' i]"], config.CANDIDATE_PORTFOLIO),
    ]
    for selectors, value in field_map:
        if not value:
            continue
        for selector in selectors:
            try:
                el = await page.query_selector(selector)
                if el:
                    await el.triple_click()
                    await el.type(value, delay=random.randint(30, 80))
                    break
            except Exception:
                continue


async def handle_captcha_detected(page, application_id: int, db) -> None:
    """Mark application as captcha_required and notify."""
    logger.warning("CAPTCHA detected during submission", extra={"application_id": application_id})
    db.update_application_status(application_id, "captcha_required",
                                  notes="CAPTCHA detected during Playwright submission")


def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password for Workday accounts."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.isupper() for c in pw) and any(c.islower() for c in pw)
                and any(c.isdigit() for c in pw) and any(c in "!@#$%" for c in pw)):
            return pw
