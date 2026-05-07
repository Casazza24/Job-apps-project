"""
Standalone job scorer — can be used independently of full orchestration.
"""
from typing import Optional
from agents.orchestrator.orchestrator import call_gemini, load_base_resume
from shared.config import get_config
from shared.logger import get_logger

logger = get_logger("scorer")


def score_job(job: dict) -> Optional[int]:
    """Quick score for a single job. Returns 0-100 or None on error."""
    config = get_config()
    base_resume = load_base_resume(config)
    result = call_gemini(job, base_resume, config)
    if result:
        return int(result.get("match_score", 0))
    return None
