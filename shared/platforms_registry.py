"""
Platform Registry — add new platforms here.

To add a new platform:
1. Create agents/scraper/platforms/yourplatform.py implementing BaseScraper
2. Create agents/submitter/platforms/yourplatform.py implementing BaseSubmitter
3. Add YOURPLATFORM_EMAIL and YOURPLATFORM_PASSWORD to .env / GCP Secret Manager
4. Add an entry to PLATFORMS below

The 'credential_prefix' maps to env vars: {prefix}_EMAIL and {prefix}_PASSWORD
"""

from agents.scraper.platforms.linkedin import LinkedInScraper
from agents.scraper.platforms.indeed import IndeedScraper
from agents.scraper.platforms.handshake import HandshakeScraper
from agents.scraper.platforms.glassdoor import GlassdoorScraper
from agents.scraper.platforms.greenhouse import GreenhouseScraper
from agents.scraper.platforms.workday import WorkdayScraper

from agents.submitter.platforms.linkedin import LinkedInSubmitter
from agents.submitter.platforms.indeed import IndeedSubmitter
from agents.submitter.platforms.handshake import HandshakeSubmitter
from agents.submitter.platforms.glassdoor import GlassdoorSubmitter
from agents.submitter.platforms.greenhouse import GreenhouseSubmitter
from agents.submitter.platforms.workday import WorkdaySubmitter

PLATFORMS = {
    "linkedin": {
        "scraper": LinkedInScraper,
        "submitter": LinkedInSubmitter,
        "credential_prefix": "LINKEDIN",   # reads LINKEDIN_EMAIL + LINKEDIN_PASSWORD
        "enabled": True,
    },
    "indeed": {
        "scraper": IndeedScraper,
        "submitter": IndeedSubmitter,
        "credential_prefix": "INDEED",
        "enabled": True,
    },
    "handshake": {
        "scraper": HandshakeScraper,
        "submitter": HandshakeSubmitter,
        "credential_prefix": "HANDSHAKE",
        "enabled": True,
    },
    "glassdoor": {
        "scraper": GlassdoorScraper,
        "submitter": GlassdoorSubmitter,
        "credential_prefix": "GLASSDOOR",
        "enabled": True,
    },
    "greenhouse": {
        "scraper": GreenhouseScraper,
        "submitter": GreenhouseSubmitter,
        "credential_prefix": "GREENHOUSE",
        "enabled": True,
    },
    "workday": {
        "scraper": WorkdayScraper,
        "submitter": WorkdaySubmitter,
        "credential_prefix": "WORKDAY",    # Workday uses auto-register, but prefix still used for base email
        "enabled": True,
    },
}


def get_enabled_scrapers():
    return {name: cfg for name, cfg in PLATFORMS.items() if cfg["enabled"]}


def get_submitter_for_platform(platform_name: str):
    cfg = PLATFORMS.get(platform_name)
    if not cfg:
        raise ValueError(f"Unknown platform: {platform_name}")
    return cfg["submitter"]
