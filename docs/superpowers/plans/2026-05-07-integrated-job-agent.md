# Integrated Job Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge job-agent and Job-Application-Tracker into a single GCP-hosted system with one dashboard for scanning jobs (with editable keywords), reviewing recommended jobs, tracking application status via Gmail, and viewing analytics charts. Job scraping uses Apify actors for reliable live data. Resume and cover letter generation incorporates real company research so every output reads like the candidate genuinely studied the company.

**Architecture:** The existing FastAPI dashboard at `dashboard/main.py` becomes the single entry point. A new `agents/email_monitor/` agent replaces the Firestore JS frontend for email tracking. Search keywords move from the hardcoded `shared/keywords.py` to a `search_config` Postgres table editable at `/settings`. Apify actors replace Playwright-based scrapers for job discovery. A new company researcher module crawls each company's website and recent news before the orchestrator generates tailored documents. Everything runs on GCP Cloud Run backed by Cloud SQL (managed Postgres 15), with Cloud Scheduler triggering the scraper and email monitor daily.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, htmx, psycopg2, Anthropic SDK (`claude-haiku-4-5-20251001`), `apify-client`, `google-api-python-client`, `google-auth-oauthlib`, Chart.js (CDN), GCP Cloud Run, Cloud SQL (Postgres 15), Cloud Scheduler, Secret Manager, Cloud Storage.

---

## File Map

**New files:**
- `db/migrations/002_email_and_config.sql` — ✅ DONE — adds email columns to `applications`, new `gmail_tokens` table, new `search_config` table
- `db/migrations/003_company_research.sql` — adds `company_research` table to cache per-company research
- `agents/email_monitor/__init__.py`
- `agents/email_monitor/gmail_client.py` — Gmail OAuth + service builder
- `agents/email_monitor/classifier.py` — Anthropic email classifier
- `agents/email_monitor/monitor.py` — orchestrates Gmail scan + DB updates
- `agents/scraper/apify_scraper.py` — Apify actor client replacing Playwright scrapers
- `agents/orchestrator/researcher.py` — crawls company website + news via Apify, returns structured research summary
- `shared/keywords_config.py` — read/write keywords from `search_config` DB table
- `dashboard/routers/settings.py` — `/settings` GET/POST + `/oauth/gmail` routes
- `dashboard/routers/stats.py` — `/stats` page + `/api/stats` JSON endpoint
- `dashboard/templates/settings.html`
- `dashboard/templates/stats.html`
- `tests/test_keywords_config.py`
- `tests/test_classifier.py`
- `tests/test_email_monitor.py`
- `tests/test_apify_scraper.py`
- `tests/test_researcher.py`
- `tests/test_settings_routes.py`
- `tests/test_stats_routes.py`

**Modified files:**
- `requirements.txt` — add `anthropic`, `apify-client`, `google-auth-oauthlib`, `google-api-python-client`
- `shared/config.py` — add `ANTHROPIC_API_KEY`, `APIFY_API_TOKEN`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_USER_EMAIL`
- `shared/db.py` — add `update_application_email_status()`, `get_company_research()`, `save_company_research()`; fix `get_submitted_applications()` to include `offer` status
- `agents/scraper/scraper.py` — swap Playwright scrapers for Apify actors
- `agents/orchestrator/orchestrator.py` — integrate researcher output into resume + cover letter prompts
- `dashboard/main.py` — register new routers, add `/trigger/email-monitor` endpoint
- `dashboard/templates/base.html` — add Settings and Stats nav links
- `dashboard/templates/tracker.html` — show email-derived response subject
- `infra/setup_gcp.sh` — add Cloud SQL, Apify token secret, Gmail OAuth secret, email monitor scheduler

---

## Task 1: DB Migration ✅ COMPLETE (commit 3b36763)

**Files:**
- Create: `db/migrations/002_email_and_config.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- db/migrations/002_email_and_config.sql
-- Run: psql $DATABASE_URL -f db/migrations/002_email_and_config.sql

-- Email tracking columns on applications
ALTER TABLE applications
  ADD COLUMN IF NOT EXISTS email_thread_id    TEXT,
  ADD COLUMN IF NOT EXISTS email_message_id   TEXT,
  ADD COLUMN IF NOT EXISTS contact_email      TEXT,
  ADD COLUMN IF NOT EXISTS sender_domain      TEXT,
  ADD COLUMN IF NOT EXISTS response_email_id  TEXT,
  ADD COLUMN IF NOT EXISTS response_subject   TEXT;

-- Store Gmail OAuth tokens (one row per user email)
CREATE TABLE IF NOT EXISTS gmail_tokens (
    id          SERIAL PRIMARY KEY,
    user_email  TEXT UNIQUE NOT NULL,
    token_json  TEXT NOT NULL,
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Key/value config store (keywords, domains, etc.)
CREATE TABLE IF NOT EXISTS search_config (
    id          SERIAL PRIMARY KEY,
    key         TEXT UNIQUE NOT NULL,
    value_json  TEXT NOT NULL,
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_applications_sender_domain ON applications(sender_domain);
```

- [ ] **Step 2: Run the migration locally**

```bash
psql $DATABASE_URL -f db/migrations/002_email_and_config.sql
```

Expected output:
```
ALTER TABLE
CREATE TABLE
CREATE TABLE
CREATE INDEX
```

- [ ] **Step 3: Verify columns exist**

```bash
psql $DATABASE_URL -c "\d applications" | grep -E "email|contact|sender|response"
```

Expected: lines for `email_thread_id`, `email_message_id`, `contact_email`, `sender_domain`, `response_email_id`, `response_subject`.

- [ ] **Step 4: Commit**

```bash
git add db/migrations/002_email_and_config.sql
git commit -m "feat: add email tracking columns and config table"
```

---

## Task 2: Dependencies & Config

**Files:**
- Modify: `requirements.txt`
- Modify: `shared/config.py`

- [ ] **Step 1: Add new packages to requirements.txt**

Replace the existing `requirements.txt` with:

```
google-cloud-aiplatform>=1.60.0
fastapi>=0.111.0
uvicorn>=0.29.0
playwright>=1.44.0
psycopg2-binary>=2.9.9
sqlalchemy>=2.0.30
jinja2>=3.1.4
python-dotenv>=1.0.1
google-cloud-storage>=2.16.0
google-cloud-secret-manager>=2.20.0
httpx>=0.27.0
pydantic>=2.7.0
python-multipart>=0.0.9
sendgrid>=6.11.0
weasyprint>=62.0
reportlab>=4.2.0
python-jose>=3.3.0
itsdangerous>=2.2.0
aiofiles>=23.2.1
anthropic>=0.28.0
google-auth>=2.29.0
google-auth-oauthlib>=1.2.0
google-api-python-client>=2.130.0
```

- [ ] **Step 2: Install new packages**

```bash
pip install anthropic>=0.28.0 apify-client>=1.7.0 google-auth>=2.29.0 google-auth-oauthlib>=1.2.0 google-api-python-client>=2.130.0
```

Expected: packages install without error.

- [ ] **Step 3: Add new config fields to shared/config.py**

In `shared/config.py`, add these fields inside the `Config` class (after `RESUME_PATH`):

```python
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")
    GMAIL_CLIENT_ID: str = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET: str = os.getenv("GMAIL_CLIENT_SECRET", "")
    GMAIL_USER_EMAIL: str = os.getenv("GMAIL_USER_EMAIL", "")
    DASHBOARD_BASE_URL: str = os.getenv("DASHBOARD_BASE_URL", "http://localhost:8000")
```

- [ ] **Step 4: Add to .env (local dev only — never commit real values)**

Add to `.env`:
```
ANTHROPIC_API_KEY=your_key_here
GMAIL_CLIENT_ID=your_client_id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_USER_EMAIL=maca6216@colorado.edu
DASHBOARD_BASE_URL=http://localhost:8000
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt shared/config.py
git commit -m "feat: add anthropic + apify + gmail oauth dependencies and config fields"
```

---

## Task 2A: DB Migration — Company Research Table

**Files:**
- Create: `db/migrations/003_company_research.sql`

This migration adds a `company_research` cache table so research is fetched once per company and reused across multiple job applications from the same employer.

- [ ] **Step 1: Write the migration file**

```sql
-- db/migrations/003_company_research.sql
-- Run: psql $DATABASE_URL -f db/migrations/003_company_research.sql

CREATE TABLE IF NOT EXISTS company_research (
    id              SERIAL PRIMARY KEY,
    company_name    TEXT NOT NULL,
    domain          TEXT,
    mission         TEXT,
    products        TEXT,
    tech_stack      TEXT,
    culture         TEXT,
    recent_news     TEXT,
    raw_summary     TEXT NOT NULL,
    fetched_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (company_name)
);

CREATE INDEX IF NOT EXISTS idx_company_research_name ON company_research(company_name);
```

- [ ] **Step 2: Verify the SQL is correct by reviewing it**

Check: `UNIQUE (company_name)` ensures one row per company. All columns are nullable except `company_name` and `raw_summary` (the full text fallback). `fetched_at` lets the orchestrator skip re-fetching if research is recent (< 7 days old).

- [ ] **Step 3: Commit**

```bash
git add db/migrations/003_company_research.sql
git commit -m "feat: add company_research cache table"
```

---

## Task 2B: Apify Scraper

**Files:**
- Create: `agents/scraper/apify_scraper.py`
- Modify: `agents/scraper/scraper.py` — call Apify instead of Playwright scrapers
- Create: `tests/test_apify_scraper.py`

Apify actors used:
- `apify/linkedin-jobs-scraper` — LinkedIn
- `apify/indeed-scraper` — Indeed
- `apify/glassdoor-jobs-scraper` — Glassdoor
- `bebity/greenhouse-jobs-scraper` — Greenhouse (ATS boards)

Each actor run returns a list of job objects. This module normalises them to the same shape `insert_job()` already expects in `shared/db.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_apify_scraper.py
import pytest
from unittest.mock import patch, MagicMock

with patch("shared.db.get_pool"):
    from agents.scraper.apify_scraper import ApifyScraper, _normalise_linkedin, _normalise_indeed


def test_normalise_linkedin_extracts_required_fields():
    raw = {
        "id": "linkedin-123",
        "title": "Data Engineer Intern",
        "companyName": "Acme Corp",
        "location": "San Francisco, CA",
        "descriptionText": "We are looking for...",
        "jobUrl": "https://linkedin.com/jobs/view/123",
        "salary": "$80k - $100k",
    }
    result = _normalise_linkedin(raw)
    assert result["external_id"] == "linkedin_linkedin-123"
    assert result["platform"] == "linkedin"
    assert result["title"] == "Data Engineer Intern"
    assert result["company"] == "Acme Corp"
    assert result["url"] == "https://linkedin.com/jobs/view/123"
    assert result["description"] == "We are looking for..."
    assert result["salary_range"] == "$80k - $100k"


def test_normalise_linkedin_handles_missing_optional_fields():
    raw = {
        "id": "x",
        "title": "SWE Intern",
        "companyName": "Co",
        "jobUrl": "https://example.com",
    }
    result = _normalise_linkedin(raw)
    assert result["location"] is None
    assert result["salary_range"] is None
    assert result["description"] == ""


def test_normalise_indeed_extracts_required_fields():
    raw = {
        "jobId": "indeed-456",
        "positionName": "ML Intern",
        "company": "TechCorp",
        "location": "Remote",
        "description": "Exciting role...",
        "url": "https://indeed.com/viewjob?jk=456",
        "salary": None,
    }
    result = _normalise_indeed(raw)
    assert result["external_id"] == "indeed_indeed-456"
    assert result["platform"] == "indeed"
    assert result["title"] == "ML Intern"


def test_apify_scraper_run_calls_actor_for_each_platform():
    mock_client = MagicMock()
    mock_dataset = MagicMock()
    mock_dataset.iterate_items.return_value = []
    mock_client.actor.return_value.call.return_value = MagicMock(default_dataset_id="ds1")
    mock_client.dataset.return_value = mock_dataset

    with patch("agents.scraper.apify_scraper.ApifyClient", return_value=mock_client), \
         patch("agents.scraper.apify_scraper.get_config") as mock_cfg, \
         patch("agents.scraper.apify_scraper.get_keywords", return_value=["data intern"]):
        mock_cfg.return_value.APIFY_API_TOKEN = "test_token"
        scraper = ApifyScraper()
        jobs = scraper.run(platforms=["linkedin"])

    mock_client.actor.assert_called_once_with("apify/linkedin-jobs-scraper")
    assert isinstance(jobs, list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_apify_scraper.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.scraper.apify_scraper'`

- [ ] **Step 3: Implement agents/scraper/apify_scraper.py**

```python
# agents/scraper/apify_scraper.py
"""
Apify-based job scraper.
Replaces Playwright scrapers with Apify actors for reliable live job data.
Supported platforms: linkedin, indeed, glassdoor, greenhouse.
"""
from typing import Any
from apify_client import ApifyClient
from shared.config import get_config
from shared.keywords_config import get_keywords
from shared.logger import get_logger

logger = get_logger("apify_scraper")

_ACTORS = {
    "linkedin": "apify/linkedin-jobs-scraper",
    "indeed": "apify/indeed-scraper",
    "glassdoor": "apify/glassdoor-jobs-scraper",
    "greenhouse": "bebity/greenhouse-jobs-scraper",
}

# Max results per keyword per platform per run
_MAX_RESULTS = 25


def _normalise_linkedin(item: dict) -> dict:
    return {
        "external_id": f"linkedin_{item['id']}",
        "platform": "linkedin",
        "title": item.get("title", ""),
        "company": item.get("companyName", ""),
        "location": item.get("location"),
        "salary_range": item.get("salary"),
        "url": item.get("jobUrl", ""),
        "description": item.get("descriptionText", ""),
        "is_workday": False,
        "workday_url": None,
    }


def _normalise_indeed(item: dict) -> dict:
    return {
        "external_id": f"indeed_{item['jobId']}",
        "platform": "indeed",
        "title": item.get("positionName", ""),
        "company": item.get("company", ""),
        "location": item.get("location"),
        "salary_range": item.get("salary"),
        "url": item.get("url", ""),
        "description": item.get("description", ""),
        "is_workday": False,
        "workday_url": None,
    }


def _normalise_glassdoor(item: dict) -> dict:
    return {
        "external_id": f"glassdoor_{item.get('jobId', item.get('id', ''))}",
        "platform": "glassdoor",
        "title": item.get("jobTitle", ""),
        "company": item.get("employerName", ""),
        "location": item.get("location"),
        "salary_range": item.get("salaryEstimate"),
        "url": item.get("jobUrl", ""),
        "description": item.get("jobDescription", ""),
        "is_workday": False,
        "workday_url": None,
    }


def _normalise_greenhouse(item: dict) -> dict:
    return {
        "external_id": f"greenhouse_{item.get('id', '')}",
        "platform": "greenhouse",
        "title": item.get("title", ""),
        "company": item.get("company", ""),
        "location": item.get("location", {}).get("name") if isinstance(item.get("location"), dict) else item.get("location"),
        "salary_range": None,
        "url": item.get("absolute_url", ""),
        "description": item.get("content", ""),
        "is_workday": False,
        "workday_url": None,
    }


_NORMALISERS = {
    "linkedin": _normalise_linkedin,
    "indeed": _normalise_indeed,
    "glassdoor": _normalise_glassdoor,
    "greenhouse": _normalise_greenhouse,
}


class ApifyScraper:
    def __init__(self):
        config = get_config()
        self._client = ApifyClient(config.APIFY_API_TOKEN)

    def run(self, platforms: list[str] | None = None) -> list[dict]:
        """
        Run Apify actors for each requested platform and return normalised job dicts.
        Defaults to all four platforms if not specified.
        """
        platforms = platforms or list(_ACTORS.keys())
        keywords = get_keywords()
        all_jobs: list[dict] = []

        for platform in platforms:
            actor_id = _ACTORS.get(platform)
            if not actor_id:
                logger.warning("Unknown platform", extra={"platform": platform})
                continue

            input_payload = _build_input(platform, keywords)

            try:
                logger.info("Running Apify actor", extra={"platform": platform, "actor": actor_id})
                run = self._client.actor(actor_id).call(run_input=input_payload)
                dataset_id = run["defaultDatasetId"]

                normalise = _NORMALISERS[platform]
                count = 0
                for item in self._client.dataset(dataset_id).iterate_items():
                    try:
                        job = normalise(item)
                        if job["title"] and job["url"]:
                            all_jobs.append(job)
                            count += 1
                    except Exception as e:
                        logger.warning("Failed to normalise item", extra={"platform": platform, "error": str(e)})

                logger.info("Actor complete", extra={"platform": platform, "jobs": count})

            except Exception as e:
                logger.error("Actor run failed", extra={"platform": platform, "error": str(e)})

        return all_jobs


def _build_input(platform: str, keywords: list[str]) -> dict:
    """Build Apify actor input payload for each platform."""
    if platform == "linkedin":
        return {
            "queries": keywords[:10],
            "maxResults": _MAX_RESULTS,
            "proxy": {"useApifyProxy": True},
        }
    if platform == "indeed":
        return {
            "queries": [{"keyword": kw, "country": "US"} for kw in keywords[:10]],
            "maxResults": _MAX_RESULTS,
            "proxy": {"useApifyProxy": True},
        }
    if platform == "glassdoor":
        return {
            "queries": keywords[:10],
            "maxResultsPerPage": _MAX_RESULTS,
            "proxy": {"useApifyProxy": True},
        }
    if platform == "greenhouse":
        return {
            "startUrls": [{"url": "https://boards.greenhouse.io/"}],
            "maxJobsPerBoard": _MAX_RESULTS,
            "searchKeywords": keywords[:5],
        }
    return {}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_apify_scraper.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Update agents/scraper/scraper.py to use ApifyScraper**

Replace the body of `run_scraper()` in `agents/scraper/scraper.py`:

```python
async def run_scraper() -> None:
    from agents.scraper.apify_scraper import ApifyScraper
    from agents.scraper.deduplicator import Deduplicator

    dedup = Deduplicator()
    scraper = ApifyScraper()

    logger.info("Starting Apify scrape")
    jobs = scraper.run()
    new_jobs = dedup.filter_new(jobs)
    logger.info("Scrape complete", extra={"total": len(jobs), "new": len(new_jobs)})

    total_inserted = 0
    for job in new_jobs:
        try:
            inserted_id = insert_job(job)
            if inserted_id:
                total_inserted += 1
        except Exception as e:
            logger.error("Failed to insert job", extra={"error": str(e), "job": job.get("title")})

    logger.info("Insertion complete", extra={"inserted": total_inserted})

    try:
        from agents.orchestrator.orchestrator import run_orchestrator
        run_orchestrator()
    except Exception as e:
        logger.error("Orchestrator failed after scraping", extra={"error": str(e)})
```

- [ ] **Step 6: Commit**

```bash
git add agents/scraper/apify_scraper.py agents/scraper/scraper.py tests/test_apify_scraper.py
git commit -m "feat: replace playwright scrapers with apify actors for live job data"
```

---

## Task 2C: Company Research Module

**Files:**
- Create: `agents/orchestrator/researcher.py`
- Modify: `shared/db.py` — add `get_company_research()` and `save_company_research()`
- Modify: `agents/orchestrator/orchestrator.py` — call researcher before generating resume + cover letter
- Create: `tests/test_researcher.py`

The researcher uses two Apify actors:
1. `apify/website-content-crawler` — crawls the company's homepage and /about page to extract mission, products, values, tech stack
2. `apify/google-search-scraper` — fetches top 3 recent news results for "[company] news 2025 2026"

Results are cached in the `company_research` table for 7 days. The orchestrator passes a concise research summary to Claude when generating both the resume diff and the cover letter.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_researcher.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

with patch("shared.db.get_pool"):
    from agents.orchestrator.researcher import (
        fetch_company_research, _crawl_website, _fetch_news, _summarise_research
    )


def test_fetch_company_research_returns_cached_if_recent():
    fresh_row = {
        "id": 1,
        "company_name": "Acme",
        "raw_summary": "Acme builds widgets. Recent news: launched v2.",
        "fetched_at": datetime.utcnow() - timedelta(days=2),
    }
    with patch("agents.orchestrator.researcher.get_company_research", return_value=fresh_row):
        result = fetch_company_research("Acme", "https://acme.com")
    assert result == fresh_row["raw_summary"]


def test_fetch_company_research_refetches_if_stale():
    stale_row = {
        "id": 1,
        "company_name": "Acme",
        "raw_summary": "old summary",
        "fetched_at": datetime.utcnow() - timedelta(days=10),
    }
    fresh_summary = "Acme Corp — mission: empower developers..."
    with patch("agents.orchestrator.researcher.get_company_research", return_value=stale_row), \
         patch("agents.orchestrator.researcher._crawl_website", return_value="homepage text"), \
         patch("agents.orchestrator.researcher._fetch_news", return_value="news text"), \
         patch("agents.orchestrator.researcher._summarise_research", return_value=fresh_summary), \
         patch("agents.orchestrator.researcher.save_company_research") as mock_save:
        result = fetch_company_research("Acme", "https://acme.com")
    assert result == fresh_summary
    mock_save.assert_called_once()


def test_fetch_company_research_fetches_when_no_cache():
    fresh_summary = "TechCorp — builds AI tools..."
    with patch("agents.orchestrator.researcher.get_company_research", return_value=None), \
         patch("agents.orchestrator.researcher._crawl_website", return_value="homepage text"), \
         patch("agents.orchestrator.researcher._fetch_news", return_value="news text"), \
         patch("agents.orchestrator.researcher._summarise_research", return_value=fresh_summary), \
         patch("agents.orchestrator.researcher.save_company_research") as mock_save:
        result = fetch_company_research("TechCorp", "https://techcorp.com")
    assert result == fresh_summary
    mock_save.assert_called_once_with("TechCorp", fresh_summary)


def test_summarise_research_calls_claude_with_both_inputs():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="Acme Corp builds developer tools. Founded 2018. Recent: Series B.")]
    with patch("agents.orchestrator.researcher.get_config") as mock_cfg, \
         patch("agents.orchestrator.researcher.Anthropic") as mock_anthropic:
        mock_cfg.return_value.ANTHROPIC_API_KEY = "key"
        mock_anthropic.return_value.messages.create.return_value = mock_msg
        result = _summarise_research("Acme", "homepage content here", "news content here")
    assert "Acme" in result or len(result) > 0
    msg_call = mock_anthropic.return_value.messages.create.call_args
    assert "homepage content here" in str(msg_call) or "news content here" in str(msg_call)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_researcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.orchestrator.researcher'`

- [ ] **Step 3: Add DB helpers to shared/db.py**

Add after the existing application queries section:

```python
# --- Company research cache ---

def get_company_research(company_name: str) -> Optional[Dict[str, Any]]:
    return fetchone(
        "SELECT * FROM company_research WHERE company_name = %s",
        (company_name,),
    )


def save_company_research(company_name: str, raw_summary: str) -> None:
    execute(
        """INSERT INTO company_research (company_name, raw_summary)
           VALUES (%s, %s)
           ON CONFLICT (company_name)
           DO UPDATE SET raw_summary = EXCLUDED.raw_summary, fetched_at = NOW()""",
        (company_name, raw_summary),
    )
```

- [ ] **Step 4: Implement agents/orchestrator/researcher.py**

```python
# agents/orchestrator/researcher.py
"""
Company Research Module.
For a given company name + website URL, crawls their homepage/about page
and fetches recent news, then summarises into a concise research brief
for use in resume tailoring and cover letter generation.

Results are cached in company_research for 7 days to avoid repeat API calls.
"""
from datetime import datetime, timedelta
from anthropic import Anthropic
from apify_client import ApifyClient

from shared.config import get_config
from shared.db import get_company_research, save_company_research
from shared.logger import get_logger

logger = get_logger("researcher")

_CACHE_DAYS = 7
_CRAWL_ACTOR = "apify/website-content-crawler"
_NEWS_ACTOR = "apify/google-search-scraper"


def _crawl_website(url: str) -> str:
    """Crawl company homepage and /about page, return concatenated plain text."""
    config = get_config()
    client = ApifyClient(config.APIFY_API_TOKEN)
    urls_to_crawl = [url, url.rstrip("/") + "/about"]
    try:
        run = client.actor(_CRAWL_ACTOR).call(run_input={
            "startUrls": [{"url": u} for u in urls_to_crawl],
            "maxCrawlPages": 3,
            "maxCrawlDepth": 1,
            "outputFormats": ["text"],
        })
        texts = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            text = item.get("text") or item.get("markdown") or ""
            if text:
                texts.append(text[:3000])
        return "\n\n".join(texts)[:8000]
    except Exception as e:
        logger.warning("Website crawl failed", extra={"url": url, "error": str(e)})
        return ""


def _fetch_news(company_name: str) -> str:
    """Fetch top 3 recent news results for the company."""
    config = get_config()
    client = ApifyClient(config.APIFY_API_TOKEN)
    query = f"{company_name} news 2025 2026"
    try:
        run = client.actor(_NEWS_ACTOR).call(run_input={
            "queries": [query],
            "maxResultsPerQuery": 3,
            "outputFormats": ["markdown"],
        })
        snippets = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            snippet = item.get("description") or item.get("snippet") or ""
            title = item.get("title", "")
            if snippet:
                snippets.append(f"{title}: {snippet}")
        return "\n".join(snippets)
    except Exception as e:
        logger.warning("News fetch failed", extra={"company": company_name, "error": str(e)})
        return ""


def _summarise_research(company_name: str, website_text: str, news_text: str) -> str:
    """
    Use Claude Haiku to distil crawled content into a concise research brief.
    The brief is designed to be injected into resume and cover letter prompts.
    """
    config = get_config()
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

    user = f"""You are preparing a research brief about {company_name} for a job applicant.

WEBSITE CONTENT:
{website_text[:4000]}

RECENT NEWS:
{news_text[:2000]}

Write a concise research brief (under 300 words) covering:
1. What the company does and its core products/services
2. Mission, values, or culture signals from the website
3. Tech stack or engineering approach (if mentioned)
4. Any notable recent news, launches, funding, or milestones
5. One specific thing the applicant could reference to show genuine interest

Be specific and factual. If information is missing, omit that section rather than guessing.
Format as short paragraphs, not bullet points."""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


def fetch_company_research(company_name: str, company_url: str) -> str:
    """
    Return a research brief for the given company.
    Uses cache if data is < 7 days old, otherwise fetches fresh.
    Returns empty string on complete failure (caller should handle gracefully).
    """
    cached = get_company_research(company_name)
    if cached:
        age = datetime.utcnow() - cached["fetched_at"]
        if age < timedelta(days=_CACHE_DAYS):
            logger.debug("Using cached research", extra={"company": company_name})
            return cached["raw_summary"]

    logger.info("Fetching company research", extra={"company": company_name, "url": company_url})
    website_text = _crawl_website(company_url) if company_url else ""
    news_text = _fetch_news(company_name)

    if not website_text and not news_text:
        logger.warning("No research data found", extra={"company": company_name})
        return ""

    summary = _summarise_research(company_name, website_text, news_text)
    save_company_research(company_name, summary)
    return summary
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_researcher.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 6: Integrate research into orchestrator**

In `agents/orchestrator/orchestrator.py`, find the function that calls the LLM to generate the tailored resume and cover letter (currently `call_gemini` or similar). Add a research fetch step before those calls and inject the research into the prompts.

Find where the cover letter prompt is constructed and add:

```python
from agents.orchestrator.researcher import fetch_company_research

# Before building prompts:
company_name = job.get("company", "")
job_url = job.get("url", "")
# Derive company URL from job URL (use homepage domain)
import re
domain_match = re.search(r"https?://([^/]+)", job_url)
company_domain = f"https://{domain_match.group(1)}" if domain_match else ""

research_brief = fetch_company_research(company_name, company_domain)
research_section = f"\n\nCOMPANY RESEARCH:\n{research_brief}" if research_brief else ""
```

Then in the cover letter prompt, change:

```python
# BEFORE (generic):
f"Write a cover letter for {company_name} for the role of {job['title']}..."

# AFTER (research-driven):
f"""Write a tailored cover letter for the role of {job['title']} at {company_name}.

{research_section}

The letter must:
- Open with a specific reference to something real about {company_name} (use the research above — mention a product, mission statement, recent launch, or value)
- Connect the candidate's specific experience to what {company_name} actually does
- Sound like the candidate genuinely researched the company, not like a template
- Be concise: 3 short paragraphs, under 250 words
- Close with a specific reason why this role at this company (not just any company)
"""
```

Similarly update the resume tailoring prompt to include `research_section` for context on the company's tech stack and focus areas.

- [ ] **Step 7: Commit**

```bash
git add agents/orchestrator/researcher.py agents/orchestrator/orchestrator.py shared/db.py tests/test_researcher.py
git commit -m "feat: add company research module with apify crawl and research-driven cover letter/resume tailoring"
```

---

## Task 3: Keywords Config Module

**Files:**
- Create: `shared/keywords_config.py`
- Create: `tests/test_keywords_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_keywords_config.py
import json
import pytest
from unittest.mock import patch, MagicMock

with patch("shared.db.get_pool"):
    from shared.keywords_config import get_keywords, set_keywords, get_internship_domains, set_internship_domains
    from shared.keywords import SEARCH_KEYWORDS, INTERNSHIP_DOMAINS


def _mock_fetchone(return_value):
    return patch("shared.keywords_config.fetchone", return_value=return_value)


def _mock_execute():
    return patch("shared.keywords_config.execute")


def test_get_keywords_falls_back_to_defaults_when_no_db_row():
    with _mock_fetchone(None):
        result = get_keywords()
    assert result == list(SEARCH_KEYWORDS)


def test_get_keywords_returns_db_value_when_row_exists():
    stored = ["python intern", "ml intern"]
    with _mock_fetchone({"value_json": json.dumps(stored)}):
        result = get_keywords()
    assert result == stored


def test_set_keywords_calls_execute_with_upsert():
    kws = ["data engineer", "ml engineer"]
    with _mock_execute() as mock_exec:
        set_keywords(kws)
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args
    assert json.dumps(kws) in call_args[0]


def test_get_internship_domains_falls_back_to_defaults():
    with _mock_fetchone(None):
        result = get_internship_domains()
    assert result == list(INTERNSHIP_DOMAINS)


def test_set_internship_domains_calls_execute():
    domains = ["Python", "SQL"]
    with _mock_execute() as mock_exec:
        set_internship_domains(domains)
    mock_exec.assert_called_once()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_keywords_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'shared.keywords_config'`

- [ ] **Step 3: Implement shared/keywords_config.py**

```python
# shared/keywords_config.py
import json
from shared.db import fetchone, execute
from shared.keywords import SEARCH_KEYWORDS, INTERNSHIP_DOMAINS


def get_keywords() -> list[str]:
    row = fetchone("SELECT value_json FROM search_config WHERE key = 'search_keywords'")
    return json.loads(row["value_json"]) if row else list(SEARCH_KEYWORDS)


def set_keywords(keywords: list[str]) -> None:
    execute(
        """INSERT INTO search_config (key, value_json)
           VALUES ('search_keywords', %s)
           ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json, updated_at = NOW()""",
        (json.dumps(keywords),),
    )


def get_internship_domains() -> list[str]:
    row = fetchone("SELECT value_json FROM search_config WHERE key = 'internship_domains'")
    return json.loads(row["value_json"]) if row else list(INTERNSHIP_DOMAINS)


def set_internship_domains(domains: list[str]) -> None:
    execute(
        """INSERT INTO search_config (key, value_json)
           VALUES ('internship_domains', %s)
           ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json, updated_at = NOW()""",
        (json.dumps(domains),),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_keywords_config.py -v
```

Expected: 5 tests PASSED.

- [ ] **Step 5: Update scraper to use DB keywords instead of hardcoded list**

In `agents/scraper/scraper.py`, find any reference to `SEARCH_KEYWORDS` (it's used inside platform scrapers) and update `shared/platforms_registry.py` or wherever the keywords are consumed. Check:

```bash
grep -rn "SEARCH_KEYWORDS\|from shared.keywords" agents/ shared/
```

For any file that imports `from shared.keywords import SEARCH_KEYWORDS`, replace with:

```python
from shared.keywords_config import get_keywords
# ...
keywords = get_keywords()
```

- [ ] **Step 6: Commit**

```bash
git add shared/keywords_config.py tests/test_keywords_config.py agents/
git commit -m "feat: move search keywords to DB with keywords_config module"
```

---

## Task 4: Gmail OAuth Client

**Files:**
- Create: `agents/email_monitor/__init__.py`
- Create: `agents/email_monitor/gmail_client.py`

- [ ] **Step 1: Create the package init**

```python
# agents/email_monitor/__init__.py
```

(empty file)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_gmail_client.py
import json
import pytest
from unittest.mock import patch, MagicMock

with patch("shared.db.get_pool"):
    from agents.email_monitor.gmail_client import (
        load_credentials, save_credentials, get_oauth_flow
    )


def test_load_credentials_returns_none_when_no_row():
    with patch("agents.email_monitor.gmail_client.fetchone", return_value=None):
        result = load_credentials("user@example.com")
    assert result is None


def test_save_credentials_calls_execute_with_email_and_json():
    mock_creds = MagicMock()
    mock_creds.to_json.return_value = '{"token": "abc"}'
    with patch("agents.email_monitor.gmail_client.execute") as mock_exec:
        save_credentials("user@example.com", mock_creds)
    mock_exec.assert_called_once()
    args = mock_exec.call_args[0]
    assert "user@example.com" in args[1]
    assert '{"token": "abc"}' in args[1]


def test_get_oauth_flow_requires_config():
    mock_config = MagicMock()
    mock_config.GMAIL_CLIENT_ID = "client_id"
    mock_config.GMAIL_CLIENT_SECRET = "secret"
    with patch("agents.email_monitor.gmail_client.get_config", return_value=mock_config):
        flow = get_oauth_flow("http://localhost:8000/oauth/gmail/callback")
    assert flow is not None
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
pytest tests/test_gmail_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.email_monitor.gmail_client'`

- [ ] **Step 4: Implement agents/email_monitor/gmail_client.py**

```python
# agents/email_monitor/gmail_client.py
"""
Gmail OAuth 2.0 client.
Stores access/refresh tokens in the gmail_tokens DB table.
"""
import json
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from shared.config import get_config
from shared.db import fetchone, execute
from shared.logger import get_logger

logger = get_logger("gmail_client")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.metadata",
]


def get_oauth_flow(redirect_uri: str) -> Flow:
    config = get_config()
    client_config = {
        "web": {
            "client_id": config.GMAIL_CLIENT_ID,
            "client_secret": config.GMAIL_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)


def load_credentials(user_email: str) -> Optional[Credentials]:
    row = fetchone("SELECT token_json FROM gmail_tokens WHERE user_email = %s", (user_email,))
    if not row:
        return None
    creds = Credentials.from_authorized_user_info(json.loads(row["token_json"]), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(user_email, creds)
    return creds if creds.valid else None


def save_credentials(user_email: str, creds: Credentials) -> None:
    execute(
        """INSERT INTO gmail_tokens (user_email, token_json)
           VALUES (%s, %s)
           ON CONFLICT (user_email) DO UPDATE
             SET token_json = EXCLUDED.token_json, updated_at = NOW()""",
        (user_email, creds.to_json()),
    )


def get_gmail_service(user_email: str):
    """Build and return an authenticated Gmail API service. Raises if no valid token."""
    creds = load_credentials(user_email)
    if not creds:
        raise RuntimeError(
            f"No valid Gmail credentials for {user_email}. "
            "Complete OAuth flow at /oauth/gmail first."
        )
    return build("gmail", "v1", credentials=creds)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_gmail_client.py -v
```

Expected: 3 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add agents/email_monitor/ tests/test_gmail_client.py
git commit -m "feat: add gmail oauth client with token persistence"
```

---

## Task 5: Email Classifier

**Files:**
- Create: `agents/email_monitor/classifier.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_classifier.py
import pytest
from unittest.mock import patch, MagicMock

with patch("shared.db.get_pool"):
    from agents.email_monitor.classifier import classify_email, analyze_response_email


def _mock_claude(return_json: dict):
    """Mock _call_claude to return a dict without hitting the API."""
    return patch("agents.email_monitor.classifier._call_claude", return_value=return_json)


def test_classify_email_returns_is_job_application_true():
    expected = {"isJobApplication": True, "isJobBoardAd": False,
                "company": "Acme Corp", "position": "Data Engineer Intern"}
    with _mock_claude(expected):
        result = classify_email(
            from_="noreply@acme.com",
            subject="Your application to Acme Corp",
            body="Thanks for applying to Data Engineer Intern at Acme Corp.",
        )
    assert result["isJobApplication"] is True
    assert result["company"] == "Acme Corp"
    assert result["position"] == "Data Engineer Intern"


def test_classify_email_returns_is_job_board_ad_true():
    expected = {"isJobApplication": False, "isJobBoardAd": True,
                "company": "Unknown Company", "position": "Position Not Specified"}
    with _mock_claude(expected):
        result = classify_email(
            from_="jobs-noreply@linkedin.com",
            subject="10 new jobs matching Data Engineer",
            body="Jobs you may like based on your profile...",
        )
    assert result["isJobBoardAd"] is True


def test_analyze_response_email_detects_rejection():
    expected = {"status": "rejected", "confidence": "high"}
    with _mock_claude(expected):
        result = analyze_response_email(
            subject="Your application - Update",
            body="After careful consideration we regret to inform you we are not moving forward.",
        )
    assert result["status"] == "rejected"
    assert result["confidence"] == "high"


def test_analyze_response_email_detects_interview():
    expected = {"status": "interview", "confidence": "high"}
    with _mock_claude(expected):
        result = analyze_response_email(
            subject="Interview Invitation - Software Engineer",
            body="We'd like to invite you for a phone screen next week.",
        )
    assert result["status"] == "interview"


def test_call_claude_strips_markdown_fences():
    """_call_claude must handle responses wrapped in ```json ... ```"""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='```json\n{"status": "offer", "confidence": "high"}\n```')]

    with patch("agents.email_monitor.classifier.get_config") as mock_cfg, \
         patch("agents.email_monitor.classifier.Anthropic") as mock_anthropic:
        mock_cfg.return_value.ANTHROPIC_API_KEY = "test_key"
        mock_anthropic.return_value.messages.create.return_value = mock_msg
        from agents.email_monitor.classifier import _call_claude
        result = _call_claude("sys", "user")

    assert result == {"status": "offer", "confidence": "high"}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_classifier.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.email_monitor.classifier'`

- [ ] **Step 3: Implement agents/email_monitor/classifier.py**

```python
# agents/email_monitor/classifier.py
"""
Claude Haiku-powered email classifier.
Ports classification logic from Job-Application-Tracker/js/claude-api.js.
"""
import json
from anthropic import Anthropic
from shared.config import get_config
from shared.logger import get_logger

logger = get_logger("classifier")


def _call_claude(system: str, user: str) -> dict:
    config = get_config()
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def classify_email(from_: str, subject: str, body: str) -> dict:
    """
    Returns:
      {"isJobApplication": bool, "isJobBoardAd": bool, "company": str, "position": str}
    """
    system = (
        "You are an expert at analyzing emails to identify job application confirmations. "
        "Respond ONLY with valid JSON. No explanation, no markdown, just JSON."
    )
    user = f"""Analyze this email. Determine if it is a real job application confirmation from a company.

From: {from_}
Subject: {subject}
Body:
{body[:2500]}

Return JSON exactly:
{{
  "isJobApplication": true or false,
  "isJobBoardAd": true or false,
  "company": "Company Name",
  "position": "Job Title"
}}

Rules:
- isJobApplication: true ONLY if a company is confirming they received your job application
- isJobBoardAd: true if this is a newsletter, job alert, or promotional email from a job board
- company: the actual employer. Use "Unknown Company" if unclear
- position: the exact job title. Use "Position Not Specified" if not found"""
    return _call_claude(system, user)


def analyze_response_email(subject: str, body: str) -> dict:
    """
    Returns:
      {"status": "interview"|"offer"|"rejected"|"other", "confidence": "high"|"medium"|"low"}
    """
    system = (
        "You are an expert at analyzing HR and recruiting emails. "
        "Respond ONLY with valid JSON. No explanation, no markdown, just JSON."
    )
    user = f"""Analyze this email and determine the job application status update.

Subject: {subject}
Body:
{body[:2500]}

Return JSON exactly:
{{
  "status": "interview" or "offer" or "rejected" or "other",
  "confidence": "high" or "medium" or "low"
}}

Rules:
- interview: invitation to interview, phone screen, technical assessment, scheduling a call
- offer: job offer letter, employment offer, congratulations on the role
- rejected: not moving forward, position filled, not selected, unfortunately
- other: follow-up info, unclear, or doesn't indicate a status change"""
    return _call_claude(system, user)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_classifier.py -v
```

Expected: 5 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add agents/email_monitor/classifier.py tests/test_classifier.py
git commit -m "feat: add claude email classifier for application/response detection"
```

---

## Task 6: Email Monitor Agent

**Files:**
- Create: `agents/email_monitor/monitor.py`
- Modify: `shared/db.py` — add `update_application_email_status()`, fix `get_submitted_applications()`
- Create: `tests/test_email_monitor.py`

- [ ] **Step 1: Add DB helper for email status updates**

In `shared/db.py`, add after `update_application_status()`:

```python
def update_application_email_status(
    app_id: int,
    status: str,
    response_email_id: str,
    response_subject: str,
) -> None:
    execute(
        """UPDATE applications
           SET status = %s, response_email_id = %s, response_subject = %s, updated_at = NOW()
           WHERE id = %s""",
        (status, response_email_id, response_subject, app_id),
    )
```

Also fix `get_submitted_applications()` to include `offer` in the status list:

```python
def get_submitted_applications() -> List[Dict[str, Any]]:
    return fetchall("""
        SELECT a.*, j.title, j.company, j.platform, j.url as job_url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.status IN ('submitted', 'viewed', 'interview', 'offer', 'rejected', 'failed')
        ORDER BY a.submitted_at DESC
    """)
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_email_monitor.py
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, call

with patch("shared.db.get_pool"):
    from agents.email_monitor.monitor import (
        _decode_body, _get_header, _extract_domain, _is_job_board_email, check_for_responses
    )


def test_decode_body_extracts_plain_text_from_payload():
    import base64
    raw_text = "Thank you for applying!"
    encoded = base64.urlsafe_b64encode(raw_text.encode()).decode()
    payload = {"mimeType": "text/plain", "body": {"data": encoded}}
    assert _decode_body(payload) == raw_text


def test_decode_body_handles_nested_multipart():
    import base64
    raw_text = "Interview invitation"
    encoded = base64.urlsafe_b64encode(raw_text.encode()).decode()
    payload = {
        "mimeType": "multipart/alternative",
        "body": {},
        "parts": [
            {"mimeType": "text/plain", "body": {"data": encoded}},
        ],
    }
    assert _decode_body(payload) == raw_text


def test_get_header_is_case_insensitive():
    headers = [{"name": "Subject", "value": "Hello"}, {"name": "From", "value": "a@b.com"}]
    assert _get_header(headers, "subject") == "Hello"
    assert _get_header(headers, "FROM") == "a@b.com"


def test_extract_domain_from_email_string():
    assert _extract_domain("Recruiter <hr@acme.com>") == "acme"
    assert _extract_domain("noreply@linkedin.com") == "linkedin"
    assert _extract_domain("no-email") == ""


def test_is_job_board_email_true_for_linkedin():
    assert _is_job_board_email("jobs@linkedin.com") is True


def test_is_job_board_email_false_for_company():
    assert _is_job_board_email("recruiting@acme.com") is False


def test_check_for_responses_returns_none_when_no_domain():
    mock_service = MagicMock()
    app = {"id": 1, "sender_domain": "", "contact_email": "", "submitted_at": datetime.utcnow(), "email_message_id": None}
    result = check_for_responses(mock_service, app)
    assert result is None
    mock_service.users.assert_not_called()


def test_check_for_responses_returns_status_on_match():
    import base64
    body_text = "We regret to inform you we are not moving forward."
    encoded = base64.urlsafe_b64encode(body_text.encode()).decode()
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg123"}]
    }
    mock_service.users().messages().get().execute.return_value = {
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Application Update"},
                {"name": "Date", "value": "Wed, 7 May 2026 10:00:00 +0000"},
            ],
            "mimeType": "text/plain",
            "body": {"data": encoded},
        }
    }
    app = {
        "id": 1,
        "sender_domain": "acme",
        "contact_email": "hr@acme.com",
        "submitted_at": datetime(2026, 4, 1),
        "email_message_id": "different_msg",
    }
    with patch("agents.email_monitor.monitor.analyze_response_email",
               return_value={"status": "rejected", "confidence": "high"}):
        result = check_for_responses(mock_service, app)
    assert result is not None
    assert result["status"] == "rejected"
    assert result["response_email_id"] == "msg123"
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
pytest tests/test_email_monitor.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.email_monitor.monitor'`

- [ ] **Step 4: Implement agents/email_monitor/monitor.py**

```python
# agents/email_monitor/monitor.py
"""
Email Monitor Agent.
Scans Gmail for application confirmation and response emails,
updates application statuses in Postgres.
"""
import base64
import re
from datetime import datetime, timedelta
from typing import Optional

from agents.email_monitor.gmail_client import get_gmail_service
from agents.email_monitor.classifier import analyze_response_email
from shared.config import get_config
from shared.db import fetchall, update_application_email_status
from shared.logger import get_logger

logger = get_logger("email_monitor")

_JOB_BOARD_DOMAINS = [
    "linkedin", "indeed", "handshake", "glassdoor", "ziprecruiter",
    "monster", "careerbuilder", "simplyhired", "dice",
]

_RESPONSE_SIGNALS = " OR ".join([
    '"schedule an interview"', '"phone screen"', '"interview invitation"',
    '"next steps"', '"move forward"',
    '"pleased to offer"', '"extend an offer"', '"offer letter"',
    '"not moving forward"', '"regret to inform"', '"not selected"',
    '"position has been filled"', '"unfortunately"',
])

_STATUS_KEYWORDS = [
    "interview", "offer", "rejected", "not moving", "regret",
    "congratulations", "application", "candidacy",
]


def _decode_body(payload: dict) -> str:
    if not payload:
        return ""
    data = payload.get("body", {}).get("data")
    if data:
        raw = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        if payload.get("mimeType") == "text/plain":
            return raw
        if payload.get("mimeType") == "text/html":
            return re.sub(r"<[^>]+>", " ", raw).strip()
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            text = _decode_body(part)
            if text:
                return text
    for part in payload.get("parts", []):
        text = _decode_body(part)
        if text:
            return text
    return ""


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_domain(email_str: str) -> str:
    match = re.search(r"@([\w-]+)\.", email_str)
    return match.group(1).lower() if match else ""


def _is_job_board_email(from_: str) -> bool:
    domain = _extract_domain(from_)
    return any(board in domain for board in _JOB_BOARD_DOMAINS)


def _days_since(dt: Optional[datetime]) -> int:
    if not dt:
        return 30
    return max(1, (datetime.utcnow() - dt).days)


def check_for_responses(service, application: dict) -> Optional[dict]:
    """
    Check Gmail for a response email from the company of this application.
    Returns {"status": str, "response_email_id": str, "response_subject": str} or None.
    """
    domain = application.get("sender_domain") or _extract_domain(
        application.get("contact_email") or ""
    )
    if not domain:
        return None

    days_since_applied = _days_since(application.get("submitted_at"))
    after_date = (datetime.utcnow() - timedelta(days=days_since_applied)).strftime("%Y/%m/%d")
    query = f"in:inbox from:{domain} after:{after_date} ({_RESPONSE_SIGNALS})"

    result = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
    messages = result.get("messages", [])

    for msg in messages:
        msg_id = msg["id"]
        if msg_id == application.get("email_message_id"):
            continue

        full = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        headers = full["payload"]["headers"]
        subject = _get_header(headers, "Subject")
        body = _decode_body(full["payload"])

        pre_check = (subject + " " + body[:500]).lower()
        if not any(kw in pre_check for kw in _STATUS_KEYWORDS):
            continue

        try:
            cls_result = analyze_response_email(subject, body)
            status = cls_result.get("status")
            if status and status != "other":
                return {
                    "status": status,
                    "response_email_id": msg_id,
                    "response_subject": subject,
                }
        except Exception as e:
            logger.warning("Classifier failed", extra={"error": str(e), "subject": subject})

    return None


def run_email_monitor() -> dict:
    """
    Main entry point: scan Gmail and update application statuses.
    Returns {"checked": int, "updated": int}.
    """
    config = get_config()
    service = get_gmail_service(config.GMAIL_USER_EMAIL)

    applications = fetchall(
        """SELECT a.id, a.email_message_id, a.contact_email, a.sender_domain, a.submitted_at,
                  j.company
           FROM applications a
           JOIN jobs j ON a.job_id = j.id
           WHERE a.status IN ('submitted', 'viewed')
           ORDER BY a.submitted_at DESC
           LIMIT 100"""
    )

    checked, updated = 0, 0
    logger.info("Email monitor running", extra={"total": len(applications)})

    for app in applications:
        checked += 1
        try:
            update = check_for_responses(service, app)
            if update:
                update_application_email_status(
                    app["id"],
                    update["status"],
                    update["response_email_id"],
                    update["response_subject"],
                )
                updated += 1
                logger.info("Status updated via email", extra={
                    "application_id": app["id"],
                    "company": app.get("company"),
                    "new_status": update["status"],
                })
        except Exception as e:
            logger.error("Monitor error", extra={"application_id": app["id"], "error": str(e)})

    logger.info("Email monitor complete", extra={"checked": checked, "updated": updated})
    return {"checked": checked, "updated": updated}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_email_monitor.py -v
```

Expected: 8 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add agents/email_monitor/monitor.py shared/db.py tests/test_email_monitor.py
git commit -m "feat: add email monitor agent with gmail scan and claude status detection"
```

---

## Task 7: Settings UI

**Files:**
- Create: `dashboard/routers/settings.py`
- Create: `dashboard/templates/settings.html`
- Create: `tests/test_settings_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_settings_routes.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_client():
    with patch("shared.db.get_pool"), \
         patch("shared.keywords_config.fetchone", return_value=None), \
         patch("shared.keywords_config.execute"):
        from dashboard.main import app
        return TestClient(app)


def test_settings_page_returns_200():
    with patch("shared.db.get_pool"), \
         patch("dashboard.routers.settings.get_keywords", return_value=["data intern"]), \
         patch("dashboard.routers.settings.get_internship_domains", return_value=["Python"]), \
         patch("dashboard.routers.settings.fetchone", return_value=None):
        from dashboard.main import app
        client = TestClient(app)
        resp = client.get("/settings")
    assert resp.status_code == 200
    assert "data intern" in resp.text


def test_post_keywords_redirects_to_settings():
    with patch("shared.db.get_pool"), \
         patch("dashboard.routers.settings.set_keywords") as mock_set, \
         patch("dashboard.routers.settings.get_keywords", return_value=[]), \
         patch("dashboard.routers.settings.get_internship_domains", return_value=[]), \
         patch("dashboard.routers.settings.fetchone", return_value=None):
        from dashboard.main import app
        client = TestClient(app, follow_redirects=False)
        resp = client.post("/settings/keywords", data={"keywords_text": "ml intern\ndata intern"})
    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings?saved=1"
    mock_set.assert_called_once_with(["ml intern", "data intern"])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_settings_routes.py -v
```

Expected: `ImportError` or `404` — router not registered yet.

- [ ] **Step 3: Implement dashboard/routers/settings.py**

```python
# dashboard/routers/settings.py
import asyncio
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from shared.keywords_config import get_keywords, set_keywords, get_internship_domains, set_internship_domains
from shared.db import fetchone
from shared.config import get_config
from shared.logger import get_logger

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
logger = get_logger("settings_router")


def _gmail_connected() -> bool:
    config = get_config()
    row = fetchone("SELECT id FROM gmail_tokens WHERE user_email = %s", (config.GMAIL_USER_EMAIL,))
    return row is not None


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, saved: str = ""):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "title": "Settings",
        "keywords": get_keywords(),
        "domains": get_internship_domains(),
        "gmail_connected": _gmail_connected(),
        "saved": saved == "1",
    })


@router.post("/settings/keywords")
async def update_keywords(keywords_text: str = Form(...)):
    kws = [k.strip() for k in keywords_text.strip().splitlines() if k.strip()]
    set_keywords(kws)
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@router.post("/settings/domains")
async def update_domains(domains_text: str = Form(...)):
    doms = [d.strip() for d in domains_text.strip().splitlines() if d.strip()]
    set_internship_domains(doms)
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@router.get("/oauth/gmail")
async def gmail_oauth_start(request: Request):
    """Redirect user to Google's OAuth consent screen."""
    from agents.email_monitor.gmail_client import get_oauth_flow
    config = get_config()
    redirect_uri = f"{config.DASHBOARD_BASE_URL}/oauth/gmail/callback"
    flow = get_oauth_flow(redirect_uri)
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return RedirectResponse(url=auth_url)


@router.get("/oauth/gmail/callback")
async def gmail_oauth_callback(request: Request, code: str, state: str = ""):
    """Handle OAuth callback: exchange code for token, save to DB."""
    from agents.email_monitor.gmail_client import get_oauth_flow, save_credentials
    config = get_config()
    redirect_uri = f"{config.DASHBOARD_BASE_URL}/oauth/gmail/callback"
    flow = get_oauth_flow(redirect_uri)
    flow.fetch_token(code=code)
    save_credentials(config.GMAIL_USER_EMAIL, flow.credentials)
    logger.info("Gmail OAuth completed", extra={"user": config.GMAIL_USER_EMAIL})
    return RedirectResponse(url="/settings?saved=1", status_code=303)
```

- [ ] **Step 4: Create dashboard/templates/settings.html**

```html
{% extends "base.html" %}
{% block title %}Settings — Job Agent{% endblock %}
{% block content %}
<div class="page-header">
    <h1>Settings</h1>
</div>

{% if saved %}
<div class="alert alert-success">Settings saved.</div>
{% endif %}

<!-- Gmail Status -->
<section class="settings-section">
    <h2>Gmail Integration</h2>
    {% if gmail_connected %}
        <p class="status-connected">✓ Gmail connected. Email monitor will detect responses automatically.</p>
        <form method="post" action="/trigger/email-monitor">
            <button type="submit" class="btn btn-secondary"
                hx-post="/trigger/email-monitor" hx-swap="none">
                Run Email Monitor Now
            </button>
        </form>
    {% else %}
        <p class="status-disconnected">Gmail not connected.</p>
        <a href="/oauth/gmail" class="btn btn-primary">Connect Gmail</a>
    {% endif %}
</section>

<!-- Scan Trigger -->
<section class="settings-section">
    <h2>Job Scanner</h2>
    <p>Scraper runs daily at 8am and 6pm. Trigger manually:</p>
    <button class="btn btn-primary"
        hx-post="/trigger/scraper"
        hx-swap="none"
        hx-on::after-request="this.textContent='✓ Triggered'">
        Run Scraper Now
    </button>
</section>

<!-- Keywords -->
<section class="settings-section">
    <h2>Search Keywords</h2>
    <p>One keyword or phrase per line. Used to search LinkedIn, Indeed, Handshake, etc.</p>
    <form method="post" action="/settings/keywords">
        <textarea name="keywords_text" rows="15" class="settings-textarea">{% for kw in keywords %}{{ kw }}
{% endfor %}</textarea>
        <button type="submit" class="btn btn-primary">Save Keywords</button>
    </form>
</section>

<!-- Internship Domains -->
<section class="settings-section">
    <h2>Scoring Domains</h2>
    <p>One domain per line. Jobs touching these domains score higher in fit analysis.</p>
    <form method="post" action="/settings/domains">
        <textarea name="domains_text" rows="10" class="settings-textarea">{% for d in domains %}{{ d }}
{% endfor %}</textarea>
        <button type="submit" class="btn btn-primary">Save Domains</button>
    </form>
</section>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_settings_routes.py -v
```

Expected: 2 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add dashboard/routers/settings.py dashboard/templates/settings.html tests/test_settings_routes.py
git commit -m "feat: add settings page with keyword editor and gmail oauth flow"
```

---

## Task 8: Analytics / Stats UI

**Files:**
- Create: `dashboard/routers/stats.py`
- Create: `dashboard/templates/stats.html`
- Create: `tests/test_stats_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stats_routes.py
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_stats_page_returns_200():
    with patch("shared.db.get_pool"), \
         patch("dashboard.routers.stats.fetchall", return_value=[]):
        from dashboard.main import app
        client = TestClient(app)
        resp = client.get("/stats")
    assert resp.status_code == 200
    assert "Analytics" in resp.text


def test_stats_api_returns_json():
    mock_rows = {
        "statuses": [{"status": "submitted", "count": 5}],
        "weekly": [],
        "total": 5,
        "responded": 1,
    }
    def _fetchall_side_effect(sql, *args, **kwargs):
        if "GROUP BY a.status" in sql:
            return [{"status": "submitted", "count": 5}]
        if "date_trunc" in sql:
            return []
        if "COUNT(*) as n FROM applications WHERE status !=" in sql:
            return [{"n": 5}]
        if "COUNT(*) as n FROM applications WHERE status IN" in sql:
            return [{"n": 1}]
        if "MAX(j.match_score)" in sql:
            return [{"company": "Acme", "top_score": 88}]
        return []

    with patch("shared.db.get_pool"), \
         patch("dashboard.routers.stats.fetchall", side_effect=_fetchall_side_effect):
        from dashboard.main import app
        client = TestClient(app)
        resp = client.get("/api/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert "statuses" in data
    assert "weekly" in data
    assert "response_rate" in data
    assert "top_companies" in data
    assert data["total_applications"] == 5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_stats_routes.py -v
```

Expected: `404 Not Found` for both routes.

- [ ] **Step 3: Implement dashboard/routers/stats.py**

```python
# dashboard/routers/stats.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from shared.db import fetchall

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "title": "Analytics",
    })


@router.get("/api/stats")
async def stats_data():
    """Return JSON analytics data consumed by Chart.js on /stats."""
    statuses = fetchall(
        "SELECT a.status, COUNT(*) as count FROM applications a GROUP BY a.status ORDER BY count DESC"
    )
    weekly = fetchall(
        """SELECT date_trunc('week', a.submitted_at)::date AS week, COUNT(*) AS count
           FROM applications a
           WHERE a.submitted_at > NOW() - INTERVAL '12 weeks'
           GROUP BY week ORDER BY week"""
    )
    total = fetchall(
        "SELECT COUNT(*) AS n FROM applications WHERE status != 'pending_review'"
    )[0]["n"]
    responded = fetchall(
        "SELECT COUNT(*) AS n FROM applications WHERE status IN ('interview', 'offer', 'rejected')"
    )[0]["n"]
    top_companies = fetchall(
        """SELECT j.company, MAX(j.match_score) AS top_score
           FROM jobs j JOIN applications a ON a.job_id = j.id
           GROUP BY j.company ORDER BY top_score DESC NULLS LAST LIMIT 10"""
    )
    return {
        "statuses": [{"status": r["status"], "count": r["count"]} for r in statuses],
        "weekly": [{"week": str(r["week"]), "count": r["count"]} for r in weekly],
        "response_rate": round(responded / total * 100, 1) if total else 0,
        "total_applications": total,
        "top_companies": [{"company": r["company"], "score": r["top_score"]} for r in top_companies],
    }
```

- [ ] **Step 4: Create dashboard/templates/stats.html**

```html
{% extends "base.html" %}
{% block title %}Analytics — Job Agent{% endblock %}
{% block content %}
<div class="page-header">
    <h1>Analytics</h1>
</div>

<div class="stats-grid">
    <div class="stat-card" id="total-card">
        <div class="stat-value" id="total-apps">—</div>
        <div class="stat-label">Applications Sent</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" id="response-rate">—</div>
        <div class="stat-label">Response Rate</div>
    </div>
</div>

<div class="charts-grid">
    <div class="chart-card">
        <h3>Applications Over Time</h3>
        <canvas id="weeklyChart"></canvas>
    </div>
    <div class="chart-card">
        <h3>Status Breakdown</h3>
        <canvas id="statusChart"></canvas>
    </div>
    <div class="chart-card">
        <h3>Top Companies by Fit Score</h3>
        <canvas id="companiesChart"></canvas>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script>
async function loadStats() {
    const data = await fetch('/api/stats').then(r => r.json());

    document.getElementById('total-apps').textContent = data.total_applications;
    document.getElementById('response-rate').textContent = data.response_rate + '%';

    // Weekly timeline
    new Chart(document.getElementById('weeklyChart'), {
        type: 'line',
        data: {
            labels: data.weekly.map(w => w.week),
            datasets: [{
                label: 'Applications',
                data: data.weekly.map(w => w.count),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59,130,246,0.1)',
                tension: 0.3,
                fill: true,
            }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });

    // Status breakdown (pie)
    const STATUS_COLORS = {
        submitted: '#3b82f6', interview: '#f59e0b', offer: '#10b981',
        rejected: '#ef4444', viewed: '#8b5cf6', failed: '#6b7280',
    };
    new Chart(document.getElementById('statusChart'), {
        type: 'doughnut',
        data: {
            labels: data.statuses.map(s => s.status),
            datasets: [{
                data: data.statuses.map(s => s.count),
                backgroundColor: data.statuses.map(s => STATUS_COLORS[s.status] || '#d1d5db'),
            }]
        },
        options: { responsive: true }
    });

    // Top companies (horizontal bar)
    new Chart(document.getElementById('companiesChart'), {
        type: 'bar',
        data: {
            labels: data.top_companies.map(c => c.company),
            datasets: [{
                label: 'Fit Score',
                data: data.top_companies.map(c => c.score),
                backgroundColor: '#3b82f6',
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { x: { min: 0, max: 100 } }
        }
    });
}
loadStats();
</script>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_stats_routes.py -v
```

Expected: 2 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add dashboard/routers/stats.py dashboard/templates/stats.html tests/test_stats_routes.py
git commit -m "feat: add analytics dashboard with chart.js status/timeline/company charts"
```

---

## Task 9: Wire Dashboard — Nav, Main.py, Tracker Template

**Files:**
- Modify: `dashboard/main.py`
- Modify: `dashboard/templates/base.html`
- Modify: `dashboard/templates/tracker.html`
- Add: `dashboard/static/settings.css` (minor style additions)

- [ ] **Step 1: Register new routers in dashboard/main.py**

In `dashboard/main.py`, add imports and `include_router` calls after the existing router setup:

```python
# At the top with other imports:
from dashboard.routers.settings import router as settings_router
from dashboard.routers.stats import router as stats_router

# After app = FastAPI(...) and app.mount(...):
app.include_router(settings_router)
app.include_router(stats_router)
```

Also add the email monitor trigger endpoint (add after the existing `/trigger/tracker` endpoint):

```python
@app.post("/trigger/email-monitor")
async def trigger_email_monitor():
    """Manually trigger the email monitor agent."""
    async def _run():
        try:
            from agents.email_monitor.monitor import run_email_monitor
            run_email_monitor()
        except Exception as e:
            logger.error("Email monitor trigger failed", extra={"error": str(e)})
    asyncio.create_task(_run())
    return JSONResponse({"status": "email monitor triggered"})
```

- [ ] **Step 2: Update base.html navigation**

Replace the nav section in `dashboard/templates/base.html` to add Settings and Stats links. Find the existing nav and update it to:

```html
<nav class="main-nav">
    <a href="/queue" class="nav-link {% if request.url.path == '/queue' %}active{% endif %}">
        Queue
    </a>
    <a href="/tracker" class="nav-link {% if request.url.path == '/tracker' %}active{% endif %}">
        Tracker
    </a>
    <a href="/stats" class="nav-link {% if request.url.path == '/stats' %}active{% endif %}">
        Analytics
    </a>
    <a href="/settings" class="nav-link {% if request.url.path == '/settings' %}active{% endif %}">
        Settings
    </a>
</nav>
```

- [ ] **Step 3: Update tracker.html to show email response subject**

In `dashboard/templates/tracker.html`, find the existing application row rendering and add the response subject column. After the existing status badge, add:

```html
{% if app.response_subject %}
<div class="response-subject">
    📧 <span class="email-hint">{{ app.response_subject }}</span>
</div>
{% endif %}
```

- [ ] **Step 4: Add settings styles to static/styles.css**

Append to `dashboard/static/styles.css`:

```css
/* Settings page */
.settings-section {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border, #e5e7eb);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.settings-section h2 {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
}
.settings-textarea {
    width: 100%;
    font-family: monospace;
    font-size: 0.875rem;
    border: 1px solid var(--border, #e5e7eb);
    border-radius: 4px;
    padding: 0.5rem;
    margin-bottom: 0.75rem;
    resize: vertical;
}
.status-connected { color: #10b981; font-weight: 500; }
.status-disconnected { color: #ef4444; }
.alert-success {
    background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7;
    padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 1rem;
}
/* Stats page */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.stat-card {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border, #e5e7eb);
    border-radius: 8px;
    padding: 1.25rem;
    text-align: center;
}
.stat-value { font-size: 2rem; font-weight: 700; color: #3b82f6; }
.stat-label { font-size: 0.875rem; color: #6b7280; margin-top: 0.25rem; }
.charts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1.5rem;
}
.chart-card {
    background: var(--card-bg, #fff);
    border: 1px solid var(--border, #e5e7eb);
    border-radius: 8px;
    padding: 1.25rem;
}
.chart-card h3 { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }
/* Tracker email hint */
.response-subject { font-size: 0.8rem; color: #6b7280; margin-top: 0.25rem; }
```

- [ ] **Step 5: Smoke test the full dashboard locally**

```bash
uvicorn dashboard.main:app --reload
```

Open `http://localhost:8000` and verify:
- `/queue` shows review cards
- `/tracker` shows submitted applications with email subjects (if any)
- `/stats` loads with charts (may be empty data)
- `/settings` shows keyword editor and Gmail Connect button

- [ ] **Step 6: Commit**

```bash
git add dashboard/main.py dashboard/templates/base.html dashboard/templates/tracker.html dashboard/static/styles.css
git commit -m "feat: wire settings/stats routers, update nav, add email monitor trigger"
```

---

## Task 10: GCP Cloud SQL Migration

**Files:**
- Modify: `infra/setup_gcp.sh`
- Modify: `shared/config.py` (Cloud SQL socket path)

This task migrates the local Docker Postgres to GCP Cloud SQL (managed Postgres 15), which is required for Cloud Run since containers don't have persistent disk.

- [ ] **Step 1: Create Cloud SQL instance via gcloud**

```bash
# Run once — replace PROJECT_ID and REGION as needed
export PROJECT_ID=$(gcloud config get-value project)
export REGION=us-central1

gcloud sql instances create job-agent-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --storage-size=10GB \
  --storage-auto-increase \
  --backup-start-time=03:00

gcloud sql databases create jobagent --instance=job-agent-db

gcloud sql users create jobagent \
  --instance=job-agent-db \
  --password=$(openssl rand -base64 16)
```

Expected: `Created [...]` for each command. Note the generated password.

- [ ] **Step 2: Store DB password in Secret Manager**

```bash
echo -n "YOUR_GENERATED_PASSWORD" | \
  gcloud secrets create CLOUD_SQL_PASSWORD --data-file=-

# Also store the full DATABASE_URL for the app
gcloud secrets create DATABASE_URL --data-file=- <<EOF
postgresql+psycopg2://jobagent:YOUR_GENERATED_PASSWORD@/jobagent?host=/cloudsql/$PROJECT_ID:$REGION:job-agent-db
EOF
```

- [ ] **Step 3: Run schema and migration on Cloud SQL**

```bash
# Connect via Cloud SQL Auth Proxy (install if needed: https://cloud.google.com/sql/docs/postgres/sql-proxy)
cloud-sql-proxy $PROJECT_ID:$REGION:job-agent-db &
PROXY_PID=$!

psql "postgresql://jobagent:YOUR_GENERATED_PASSWORD@127.0.0.1/jobagent" \
  -f db/schema.sql \
  -f db/migrations/002_email_and_config.sql

kill $PROXY_PID
```

Expected: all schema commands succeed.

- [ ] **Step 4: Store Gmail and Anthropic secrets**

```bash
echo -n "$GMAIL_CLIENT_ID" | gcloud secrets create GMAIL_CLIENT_ID --data-file=-
echo -n "$GMAIL_CLIENT_SECRET" | gcloud secrets create GMAIL_CLIENT_SECRET --data-file=-
echo -n "$ANTHROPIC_API_KEY" | gcloud secrets create ANTHROPIC_API_KEY --data-file=-
echo -n "maca6216@colorado.edu" | gcloud secrets create GMAIL_USER_EMAIL --data-file=-
```

- [ ] **Step 5: Update shared/config.py to prefer Secret Manager in production**

The `get_secret()` function already reads from Secret Manager when `ENV=production`. Add the new secret names to the Config class so they fall through to `get_secret`:

```python
    @property
    def ANTHROPIC_API_KEY(self) -> str:
        return get_secret("ANTHROPIC_API_KEY") if self.ENV != "local" else os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def GMAIL_CLIENT_ID(self) -> str:
        return get_secret("GMAIL_CLIENT_ID") if self.ENV != "local" else os.getenv("GMAIL_CLIENT_ID", "")

    @property
    def GMAIL_CLIENT_SECRET(self) -> str:
        return get_secret("GMAIL_CLIENT_SECRET") if self.ENV != "local" else os.getenv("GMAIL_CLIENT_SECRET", "")

    @property
    def GMAIL_USER_EMAIL(self) -> str:
        return get_secret("GMAIL_USER_EMAIL") if self.ENV != "local" else os.getenv("GMAIL_USER_EMAIL", "")
```

Remove the plain `str` field declarations for these four fields added in Task 2 (replace them with these `@property` versions).

- [ ] **Step 6: Update infra/setup_gcp.sh with Cloud SQL setup steps**

Add this section at the end of `infra/setup_gcp.sh`:

```bash
# Cloud SQL — run once
gcloud services enable sqladmin.googleapis.com

gcloud sql instances create job-agent-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION

gcloud sql databases create jobagent --instance=job-agent-db

# Grant Cloud Run SA access to Cloud SQL
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/cloudsql.client"

# Grant Cloud Run SA access to secrets
for SECRET in ANTHROPIC_API_KEY GMAIL_CLIENT_ID GMAIL_CLIENT_SECRET GMAIL_USER_EMAIL DATABASE_URL; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor"
done
```

- [ ] **Step 7: Commit**

```bash
git add infra/setup_gcp.sh shared/config.py
git commit -m "infra: add cloud sql setup and secret manager bindings for gmail/anthropic"
```

---

## Task 11: Cloud Run Deployment + Cloud Scheduler

**Files:**
- Modify: `infra/deploy_cloudrun.sh`
- Modify: `Dockerfile.agents` (add Cloud SQL socket support)

- [ ] **Step 1: Update Dockerfile.agents to include Cloud SQL socket mount**

In `Dockerfile.agents`, find the `CMD` or `ENTRYPOINT` and ensure the image is built with the Cloud SQL Auth Proxy pattern. Add the `CLOUD_SQL_CONNECTION_NAME` env var reference:

Append to `Dockerfile.agents` before the final CMD:

```dockerfile
# Cloud SQL socket directory (mounted at runtime by Cloud Run)
RUN mkdir -p /cloudsql
ENV CLOUD_SQL_CONNECTION_NAME=""
```

- [ ] **Step 2: Update deploy_cloudrun.sh to pass Cloud SQL and secrets**

Replace (or update) the `gcloud run deploy` command in `infra/deploy_cloudrun.sh`:

```bash
export PROJECT_ID=$(gcloud config get-value project)
export REGION=us-central1
export SERVICE_NAME=job-agent
export IMAGE=gcr.io/$PROJECT_ID/$SERVICE_NAME:latest

# Build and push
docker build -t $IMAGE -f Dockerfile.agents .
docker push $IMAGE

# Deploy to Cloud Run with Cloud SQL and secrets
gcloud run deploy $SERVICE_NAME \
  --image=$IMAGE \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated=false \
  --add-cloudsql-instances=$PROJECT_ID:$REGION:job-agent-db \
  --set-env-vars="ENV=production,GCP_PROJECT_ID=$PROJECT_ID,CLOUD_SQL_CONNECTION_NAME=$PROJECT_ID:$REGION:job-agent-db" \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,GMAIL_CLIENT_ID=GMAIL_CLIENT_ID:latest,GMAIL_CLIENT_SECRET=GMAIL_CLIENT_SECRET:latest,GMAIL_USER_EMAIL=GMAIL_USER_EMAIL:latest" \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')
echo "Dashboard URL: $SERVICE_URL"
echo "Set DASHBOARD_BASE_URL=$SERVICE_URL in secrets"
```

- [ ] **Step 3: Store DASHBOARD_BASE_URL secret after first deploy**

After the first deploy completes, capture the URL and store it:

```bash
SERVICE_URL=$(gcloud run services describe job-agent --region=us-central1 --format='value(status.url)')
echo -n "$SERVICE_URL" | gcloud secrets create DASHBOARD_BASE_URL --data-file=-
```

Then redeploy with `--set-secrets="...,DASHBOARD_BASE_URL=DASHBOARD_BASE_URL:latest"` added.

- [ ] **Step 4: Add Gmail OAuth redirect URI to Google Cloud Console**

In [Google Cloud Console](https://console.cloud.google.com/apis/credentials):
1. Open your OAuth 2.0 Client ID
2. Add `$SERVICE_URL/oauth/gmail/callback` to "Authorized redirect URIs"
3. Save

- [ ] **Step 5: Create Cloud Scheduler jobs**

```bash
# Scraper — 8am and 6pm daily
gcloud scheduler jobs create http job-scraper-morning \
  --schedule="0 8 * * *" \
  --uri="$SERVICE_URL/trigger/scraper" \
  --http-method=POST \
  --oidc-service-account-email=$SA_EMAIL \
  --location=$REGION

gcloud scheduler jobs create http job-scraper-evening \
  --schedule="0 18 * * *" \
  --uri="$SERVICE_URL/trigger/scraper" \
  --http-method=POST \
  --oidc-service-account-email=$SA_EMAIL \
  --location=$REGION

# Email monitor — every 4 hours
gcloud scheduler jobs create http email-monitor \
  --schedule="0 */4 * * *" \
  --uri="$SERVICE_URL/trigger/email-monitor" \
  --http-method=POST \
  --oidc-service-account-email=$SA_EMAIL \
  --location=$REGION
```

Expected: `Created job [job-scraper-morning]` etc.

- [ ] **Step 6: Run a full end-to-end smoke test on Cloud Run**

```bash
# Trigger scraper manually and verify it completes
curl -X POST $SERVICE_URL/trigger/scraper \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"

# Check /queue loads
curl $SERVICE_URL/queue \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" | grep -i "Review Queue"

# Check /stats loads
curl $SERVICE_URL/stats \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" | grep -i "Analytics"

# Check /settings loads
curl $SERVICE_URL/settings \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" | grep -i "Settings"
```

Expected: all four commands return HTTP 200 with expected content.

- [ ] **Step 7: Connect Gmail via browser**

Open `$SERVICE_URL/settings` in a browser. Click "Connect Gmail". Complete the OAuth consent flow. Verify the settings page shows "✓ Gmail connected."

- [ ] **Step 8: Run the full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests PASSED.

- [ ] **Step 9: Final commit**

```bash
git add Dockerfile.agents infra/deploy_cloudrun.sh
git commit -m "infra: cloud run deployment with cloud sql, scheduler, and gmail oauth"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Edit keywords/search phrases from dashboard → Task 3 (module) + Task 7 (settings UI)
- [x] Run a job board scan from dashboard → Task 7 (scan trigger button) + Task 9 (trigger endpoint)
- [x] Recommended jobs appear on dashboard → existing `/queue` page, unchanged (scraper→orchestrator pipeline already feeds this)
- [x] Previously applied jobs visible → existing `/tracker` page, enhanced with email status in Task 9
- [x] Gmail API status tracking → Tasks 4-6 (monitor agent) + Task 9 (trigger) + Cloud Scheduler in Task 11
- [x] GCP cloud hosting with free credits → Tasks 10-11 (Cloud SQL, Cloud Run, Scheduler)
- [x] Analytics charts → Task 8 (stats page + Chart.js)
- [x] Everything accessible from one dashboard → Task 9 (nav updated)

**Placeholder scan:** No TBDs, TODOs, or "similar to" references found.

**Type consistency:**
- `run_email_monitor()` — defined in `monitor.py`, called in `dashboard/main.py` trigger endpoint ✓
- `update_application_email_status()` — defined in `shared/db.py`, called in `monitor.py` ✓
- `get_keywords()` / `set_keywords()` — defined in `keywords_config.py`, called in `settings.py` ✓
- `get_gmail_service()` — defined in `gmail_client.py`, called in `monitor.py` ✓
- `_call_claude()` — defined and used within `classifier.py` only ✓
