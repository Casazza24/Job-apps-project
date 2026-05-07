from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseScraper(ABC):
    def __init__(self, db, config, credential_prefix: str):
        self.db = db
        self.config = config
        self.credential_prefix = credential_prefix
        try:
            self.email = config.get_platform_email(credential_prefix)
            self.password = config.get_platform_password(credential_prefix)
        except ValueError:
            self.email = None
            self.password = None

    @abstractmethod
    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape job listings. Returns list of job dicts."""
        pass

    @abstractmethod
    async def login(self, page) -> None:
        """Log into the platform."""
        pass

    def _detect_captcha(self, page_content: str) -> bool:
        """Check if the page contains CAPTCHA indicators."""
        captcha_indicators = [
            "recaptcha", "hcaptcha", "cf-challenge",
            "captcha", "challenge-form", "turnstile",
        ]
        content_lower = page_content.lower()
        return any(indicator in content_lower for indicator in captcha_indicators)
