"""
Cover letter generation utilities.
"""
from typing import Optional
from agents.orchestrator.orchestrator import call_gemini, load_base_resume
from shared.config import get_config
from shared.logger import get_logger

logger = get_logger("cover_letter")


def generate_cover_letter(job: dict) -> Optional[str]:
    """Generate a cover letter for a job. Returns text or None."""
    config = get_config()
    base_resume = load_base_resume(config)
    result = call_gemini(job, base_resume, config)
    if result:
        return result.get("cover_letter")
    return None
