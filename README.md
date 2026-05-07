# Job Agent

Autonomous multi-agent system that scrapes job listings, tailors resumes and cover letters using the Claude API, surfaces them for human review via a web dashboard, and submits approved applications using Playwright browser automation.

## Quick Start (Local)

1. Copy `.env.example` to `.env` and fill in your credentials
2. Add your resume as plain text to `resume.txt` in the project root
3. Start Postgres: `docker-compose up -d postgres`
4. Run schema: `psql -U jobagent -d jobagent -h localhost -f db/schema.sql`
5. Start dashboard: `uvicorn dashboard.main:app --reload`
6. Run scraper manually: `python -m agents.scraper.scraper`

## Architecture

- **Scraper Agent** — Playwright-based scraper for LinkedIn, Indeed, Handshake, Glassdoor, Greenhouse, Workday
- **Orchestrator Agent** — Claude API scores job fit, tailors resume bullets, writes cover letters
- **Dashboard** — FastAPI + Jinja2 review interface (approve/skip applications)
- **Submitter Agent** — Playwright auto-fills and submits approved applications
- **Tracker Agent** — Polls application status, sends daily email summaries

## GCP Deployment

See `infra/setup_gcp.sh` for one-time setup and `infra/deploy_cloudrun.sh` for deployment.

Estimated cost: ~$13-14/month (covered by free credits for ~20 months).
