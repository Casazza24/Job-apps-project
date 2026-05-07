# AI Job Application Agent — Full Build Spec

## Overview

An autonomous multi-agent system that scrapes job listings, tailors resumes and cover letters using the Claude API, surfaces them for human review via a web dashboard, and submits approved applications using Playwright browser automation. Everything runs on GCP using free credits.

---

## Target Job Keywords

The scraper will search for the following job titles across all configured platforms:

- Data Science
- Data Engineer
- Software Engineer
- AI/ML Intern
- Data Analytics Intern

---

## Candidate Profile Inputs

The following URLs should be stored as environment variables and injected into application forms and the orchestrator prompt wherever requested:

```
CANDIDATE_LINKEDIN=https://linkedin.com/in/YOUR_HANDLE
CANDIDATE_GITHUB=https://github.com/YOUR_HANDLE
CANDIDATE_PORTFOLIO=https://yourportfolio.com
```

The base resume (PDF) should be uploaded to the Cloud Storage bucket at:
```
gs://YOUR_BUCKET_NAME/base_resume.pdf
```

---

## Target Job Platforms

| Platform     | Auth Method                        | Notes                                              |
|--------------|------------------------------------|----------------------------------------------------|
| LinkedIn     | Login with stored credentials      | Use Easy Apply where available                     |
| Indeed       | Login with stored credentials      | Direct apply + redirect to employer site           |
| Handshake    | Login with stored credentials      | Focus on intern roles                              |
| Glassdoor    | Login with stored credentials      | Scrape listings, apply via redirect                |
| Greenhouse   | Login with stored credentials      | Consistent form structure, good for automation     |
| Workday      | Auto-register per employer domain  | Each company = new account, store creds in Cloud SQL |

---

## GCP Architecture

### Services Used

| GCP Service         | Role                                                        | Est. Cost         |
|---------------------|-------------------------------------------------------------|-------------------|
| Compute Engine e2-small | Persistent VM running all agents + Playwright           | ~$13/mo           |
| Cloud Run           | FastAPI web dashboard (scales to zero when idle)            | Near zero         |
| Cloud SQL (Postgres) | Primary database OR run Postgres directly on VM to save credits | ~$10/mo or free on VM |
| Cloud Storage       | Stores tailored resumes and cover letters (PDF)             | Cents/mo          |
| Cloud Scheduler     | Triggers scraper agent twice daily via HTTP                 | Free tier (3 jobs)|
| Secret Manager      | Stores all credentials and API keys securely                | ~$0               |
| Cloud IAP           | Secure HTTPS access to dashboard without open ports         | Free              |

> **Credit-saving tip:** Skip Cloud SQL and run Postgres directly on the Compute Engine VM to eliminate the ~$10/mo Cloud SQL cost. Use `pg_dump` for backups to Cloud Storage.

### Architecture Flow

```
You (browser/phone)
        |
   Cloud IAP (HTTPS)
        |
   Cloud Run — FastAPI Dashboard
        |
   Compute Engine VM (e2-small)
   ├── Scraper Agent     (Playwright, triggered by Cloud Scheduler)
   ├── Orchestrator Agent (Claude API — scores, tailors, writes)
   ├── Submitter Agent   (Playwright, triggered by dashboard approval)
   └── Tracker Agent     (polls status, sends alerts)
        |
   ┌────────────────────────────┐
   │  Cloud SQL / Postgres (VM) │  ← jobs, applications, status, Workday creds
   │  Cloud Storage bucket      │  ← tailored PDFs, cover letters
   │  Secret Manager            │  ← LinkedIn pw, Indeed pw, Claude API key
   └────────────────────────────┘
```

---

## Project Structure

```
job-agent/
├── README.md
├── .env.example
├── docker-compose.yml          # Local dev only
├── requirements.txt
│
├── dashboard/                  # Cloud Run — FastAPI + frontend
│   ├── main.py                 # FastAPI app entrypoint
│   ├── routers/
│   │   ├── jobs.py             # GET /jobs, GET /jobs/{id}
│   │   ├── applications.py     # GET /applications, POST /approve, POST /skip
│   │   └── tracker.py          # GET /tracker
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── queue.html          # New jobs to review
│   │   ├── approve.html        # Resume diff + cover letter preview
│   │   └── tracker.html        # Application status board
│   ├── static/
│   │   └── styles.css
│   └── Dockerfile
│
├── agents/                     # Runs on Compute Engine VM
│   ├── scraper/
│   │   ├── scraper.py          # Main scraper entrypoint
│   │   ├── platforms/
│   │   │   ├── linkedin.py
│   │   │   ├── indeed.py
│   │   │   ├── handshake.py
│   │   │   ├── glassdoor.py
│   │   │   ├── greenhouse.py
│   │   │   └── workday.py
│   │   └── deduplicator.py     # Prevents re-scraping same listing
│   │
│   ├── orchestrator/
│   │   ├── orchestrator.py     # Main orchestrator entrypoint
│   │   ├── scorer.py           # Scores job match 0–100
│   │   ├── resume_tailor.py    # Rewrites resume bullets for job
│   │   └── cover_letter.py     # Generates cover letter
│   │
│   ├── submitter/
│   │   ├── submitter.py        # Main submitter entrypoint
│   │   ├── platforms/
│   │   │   ├── linkedin.py
│   │   │   ├── indeed.py
│   │   │   ├── handshake.py
│   │   │   ├── glassdoor.py
│   │   │   ├── greenhouse.py
│   │   │   └── workday.py      # Handles auto-register + login
│   │   └── form_filler.py      # Shared Playwright helpers
│   │
│   └── tracker/
│       ├── tracker.py          # Polls application status
│       └── notifier.py         # Sends email/Slack alerts
│
├── db/
│   ├── schema.sql              # Postgres schema
│   └── migrations/             # Version-controlled schema changes
│
├── shared/
│   ├── config.py               # Loads secrets from Secret Manager or .env
│   ├── gcp.py                  # Cloud Storage + Secret Manager helpers
│   ├── models.py               # Pydantic models (Job, Application, etc.)
│   └── logger.py               # Structured logging
│
└── infra/
    ├── setup_gcp.sh            # One-time GCP project setup script
    ├── deploy_cloudrun.sh      # Deploy dashboard to Cloud Run
    └── vm_startup.sh           # VM startup script (install deps, start agents)
```

---

## Database Schema

```sql
-- schema.sql

CREATE TABLE jobs (
    id              SERIAL PRIMARY KEY,
    platform        TEXT NOT NULL,           -- 'linkedin', 'indeed', etc.
    external_id     TEXT UNIQUE NOT NULL,    -- platform's own job ID
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    salary_range    TEXT,
    url             TEXT NOT NULL,
    description     TEXT,
    match_score     INTEGER,                 -- 0–100, set by orchestrator
    status          TEXT DEFAULT 'new',      -- new | reviewed | approved | skipped
    scraped_at      TIMESTAMP DEFAULT NOW(),
    reviewed_at     TIMESTAMP
);

CREATE TABLE applications (
    id                  SERIAL PRIMARY KEY,
    job_id              INTEGER REFERENCES jobs(id),
    tailored_resume_url TEXT,               -- Cloud Storage path
    cover_letter_url    TEXT,               -- Cloud Storage path
    cover_letter_text   TEXT,
    resume_diff         JSONB,              -- which bullets were changed
    status              TEXT DEFAULT 'pending_review',
    -- pending_review | approved | submitted | failed | rejected | interview
    submitted_at        TIMESTAMP,
    last_checked_at     TIMESTAMP,
    notes               TEXT
);

CREATE TABLE workday_accounts (
    id              SERIAL PRIMARY KEY,
    employer_domain TEXT UNIQUE NOT NULL,   -- e.g. 'nike.wd5.myworkdayjobs.com'
    email           TEXT NOT NULL,
    password_ref    TEXT NOT NULL,          -- Secret Manager secret name
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE follow_ups (
    id              SERIAL PRIMARY KEY,
    application_id  INTEGER REFERENCES applications(id),
    scheduled_at    TIMESTAMP,
    sent_at         TIMESTAMP,
    type            TEXT                    -- '7_day_nudge', 'status_check'
);
```

---

## Agent Implementation Details

### 1. Scraper Agent

**Trigger:** Cloud Scheduler HTTP POST → `/trigger/scraper` on FastAPI → VM runs `scraper.py`

**Flow:**
1. For each platform, launch a Playwright browser session
2. Log in using credentials fetched from Secret Manager
3. Search each keyword (`data science`, `data engineer`, `software engineer`, `AI/ML intern`, `data analytics intern`)
4. Filter: posted within last 7 days, skip already-seen `external_id`s
5. Extract: title, company, location, salary, URL, full description
6. Insert into `jobs` table with `status = 'new'`

**Playwright pattern for each platform:**

```python
# agents/scraper/platforms/linkedin.py
from playwright.async_api import async_playwright
from shared.config import get_secret

KEYWORDS = [
    "data science",
    "data engineer",
    "software engineer",
    "AI ML intern",
    "data analytics intern"
]

async def scrape_linkedin(db):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Login
        await page.goto("https://www.linkedin.com/login")
        await page.fill("#username", get_secret("LINKEDIN_EMAIL"))
        await page.fill("#password", get_secret("LINKEDIN_PASSWORD"))
        await page.click("button[type=submit]")
        await page.wait_for_load_state("networkidle")

        for keyword in KEYWORDS:
            await page.goto(f"https://www.linkedin.com/jobs/search/?keywords={keyword}&f_TPR=r604800")
            # f_TPR=r604800 = past 7 days
            await scrape_results(page, db, keyword, platform="linkedin")

        await browser.close()
```

**Workday scraping note:** Workday job boards share a consistent URL pattern (`*.myworkdayjobs.com`). The scraper should detect Workday redirect links from Indeed/Glassdoor and add them to a separate Workday queue for the submitter to handle.

---

### 2. Orchestrator Agent

**Trigger:** Runs automatically after scraper inserts new jobs

**Flow:**
1. Fetch all jobs with `status = 'new'`
2. For each job, call Claude API with the job description + base resume
3. Claude returns: match score (0–100), tailored resume bullets, cover letter
4. Generate tailored resume PDF → upload to Cloud Storage
5. Insert into `applications` table with `status = 'pending_review'`
6. Update job `status = 'reviewed'`

**Claude API call — Orchestrator system prompt:**

```python
# agents/orchestrator/orchestrator.py
import anthropic
import json

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

SYSTEM_PROMPT = """
You are a job application assistant helping a candidate apply for roles in
data science, data engineering, software engineering, AI/ML, and data analytics.

Given a job description and the candidate's base resume, you will:
1. Score the job match from 0–100 based on skills alignment
2. Rewrite the resume bullet points to mirror the job description language
   and highlight the most relevant experience. Do not fabricate experience.
3. Write a personalized cover letter (3 short paragraphs, professional tone)

The candidate's URLs to include where relevant:
- LinkedIn: {linkedin_url}
- GitHub: {github_url}
- Portfolio: {portfolio_url}

Respond ONLY in valid JSON with this structure:
{{
  "match_score": <integer 0-100>,
  "score_reasoning": "<one sentence>",
  "tailored_bullets": [
    {{"original": "...", "tailored": "..."}}
  ],
  "cover_letter": "<full cover letter text>"
}}
"""

async def process_job(job, base_resume_text, config):
    prompt = f"""
Job Title: {job['title']}
Company: {job['company']}
Job Description:
{job['description']}

Candidate Base Resume:
{base_resume_text}
"""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SYSTEM_PROMPT.format(
            linkedin_url=config.CANDIDATE_LINKEDIN,
            github_url=config.CANDIDATE_GITHUB,
            portfolio_url=config.CANDIDATE_PORTFOLIO
        ),
        messages=[{"role": "user", "content": prompt}]
    )

    result = json.loads(response.content[0].text)
    return result
```

---

### 3. Human Review Dashboard

**Hosted on:** Cloud Run (FastAPI + Jinja2 templates)
**Access via:** Cloud IAP → your Google account = secure login, no password needed

**Tabs / routes:**

| Route | Description |
|-------|-------------|
| `GET /` | Redirect to `/queue` |
| `GET /queue` | All jobs with `status = 'new'` or `'pending_review'`, sorted by match score desc |
| `GET /review/{application_id}` | Full review page: job details, match score, resume diff, cover letter |
| `POST /approve/{application_id}` | Sets status to `'approved'`, triggers submitter |
| `POST /skip/{application_id}` | Sets status to `'skipped'` |
| `GET /tracker` | All applications with current status, submitted date, follow-up schedule |

**Review page shows:**
- Job title, company, location, salary, link to original posting
- Match score (color coded: green 70+, yellow 50–69, red below 50)
- Side-by-side resume diff (original bullet → tailored bullet)
- Cover letter text (editable before approving)
- Approve / Skip buttons

**Dashboard stack:**
```
FastAPI (Python)
├── Jinja2 templates (server-side rendered, no JS framework needed)
├── htmx (for approve/skip without full page reload — lightweight)
└── Simple CSS (no Tailwind build step needed on Cloud Run)
```

---

### 4. Submitter Agent

**Trigger:** `POST /approve/{application_id}` from dashboard → VM runs `submitter.py`

**Flow:**
1. Fetch approved application + job details from DB
2. Download tailored resume PDF from Cloud Storage
3. Route to correct platform submitter based on `job.platform`
4. For Workday: check `workday_accounts` table for existing account on that domain
   - If exists: log in with stored credentials
   - If not: register new account, save credentials to DB + Secret Manager
5. Fill all form fields using Playwright
6. Upload resume PDF
7. Insert LinkedIn URL, GitHub URL, portfolio URL where fields exist
8. Submit form
9. Update `applications.status = 'submitted'`, log `submitted_at`

**Workday auto-register pattern:**

```python
# agents/submitter/platforms/workday.py
async def submit_workday(page, job, application, config, db):
    domain = extract_workday_domain(job["url"])
    account = db.get_workday_account(domain)

    await page.goto(job["url"])

    if account:
        # Log in with existing account
        await page.click("text=Sign In")
        await page.fill("input[name='username']", account["email"])
        await page.fill("input[name='password']", get_secret(account["password_ref"]))
        await page.click("button[type='submit']")
    else:
        # Register new account
        email = f"youremail+{domain.split('.')[0]}@gmail.com"  # Gmail alias trick
        password = generate_secure_password()

        await page.click("text=Create Account")
        await page.fill("input[name='email']", email)
        await page.fill("input[name='password']", password)
        await page.fill("input[name='firstName']", config.FIRST_NAME)
        await page.fill("input[name='lastName']", config.LAST_NAME)
        await page.click("button[type='submit']")

        # Save to DB and Secret Manager
        secret_name = f"workday_{domain.replace('.', '_')}"
        save_secret(secret_name, password)
        db.save_workday_account(domain, email, secret_name)

    # Fill application form
    await fill_common_fields(page, application, config)
    await upload_resume(page, application["tailored_resume_path"])
    await page.click("button[type='submit']")
```

**Gmail alias trick:** Using `youremail+nike@gmail.com`, `youremail+amazon@gmail.com` etc. keeps all Workday confirmation emails going to your one inbox, organized by company.

---

### 5. Tracker Agent

**Trigger:** Runs on a daily cron via Cloud Scheduler

**Flow:**
1. Fetch all applications with `status = 'submitted'`
2. For each, log into the platform and check application status
3. Update DB with any status changes (viewed, rejected, interview scheduled)
4. Flag applications with no update after 7 days → create a `follow_ups` record
5. Send daily summary email (via SendGrid free tier or Gmail SMTP)

---

## GCP Setup Instructions

### Step 1 — Create GCP project and enable APIs

```bash
# Set your project ID
export PROJECT_ID=job-agent-YOUR_NAME
export REGION=us-central1

gcloud projects create $PROJECT_ID
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  compute.googleapis.com \
  sql-component.googleapis.com \
  storage.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  iap.googleapis.com
```

### Step 2 — Create Cloud Storage bucket

```bash
export BUCKET_NAME=job-agent-files-YOUR_NAME

gsutil mb -l $REGION gs://$BUCKET_NAME
gsutil cp /path/to/your/base_resume.pdf gs://$BUCKET_NAME/base_resume.pdf
```

### Step 3 — Store secrets in Secret Manager

```bash
# Store each credential as a secret
echo -n "your_linkedin_email" | gcloud secrets create LINKEDIN_EMAIL --data-file=-
echo -n "your_linkedin_password" | gcloud secrets create LINKEDIN_PASSWORD --data-file=-
echo -n "your_indeed_email" | gcloud secrets create INDEED_EMAIL --data-file=-
echo -n "your_indeed_password" | gcloud secrets create INDEED_PASSWORD --data-file=-
echo -n "your_handshake_email" | gcloud secrets create HANDSHAKE_EMAIL --data-file=-
echo -n "your_handshake_password" | gcloud secrets create HANDSHAKE_PASSWORD --data-file=-
echo -n "your_glassdoor_email" | gcloud secrets create GLASSDOOR_EMAIL --data-file=-
echo -n "your_glassdoor_password" | gcloud secrets create GLASSDOOR_PASSWORD --data-file=-
echo -n "your_greenhouse_email" | gcloud secrets create GREENHOUSE_EMAIL --data-file=-
echo -n "your_greenhouse_password" | gcloud secrets create GREENHOUSE_PASSWORD --data-file=-
echo -n "your_anthropic_api_key" | gcloud secrets create ANTHROPIC_API_KEY --data-file=-
echo -n "your_candidate_name" | gcloud secrets create CANDIDATE_FIRST_NAME --data-file=-
echo -n "your_last_name" | gcloud secrets create CANDIDATE_LAST_NAME --data-file=-
```

### Step 4 — Create Compute Engine VM

```bash
gcloud compute instances create job-agent-vm \
  --zone=$REGION-a \
  --machine-type=e2-small \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=20GB \
  --scopes=cloud-platform \
  --tags=job-agent

# SSH into VM
gcloud compute ssh job-agent-vm --zone=$REGION-a
```

### Step 5 — VM startup setup (run inside VM)

```bash
# Install system dependencies
sudo apt-get update && sudo apt-get install -y \
  python3-pip python3-venv git postgresql postgresql-contrib \
  chromium chromium-driver xvfb

# Clone your repo
git clone https://github.com/YOUR_HANDLE/job-agent.git
cd job-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
playwright install-deps

# Set up local Postgres (alternative to Cloud SQL)
sudo -u postgres psql -c "CREATE DATABASE jobagent;"
sudo -u postgres psql -c "CREATE USER jobagent WITH PASSWORD 'yourpassword';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE jobagent TO jobagent;"
psql -U jobagent -d jobagent -f db/schema.sql

# Create systemd service so agents restart on VM reboot
sudo cp infra/job-agent.service /etc/systemd/system/
sudo systemctl enable job-agent
sudo systemctl start job-agent
```

### Step 6 — Deploy dashboard to Cloud Run

```bash
cd dashboard

# Build and deploy
gcloud run deploy job-agent-dashboard \
  --source . \
  --region $REGION \
  --platform managed \
  --no-allow-unauthenticated \
  --set-env-vars DATABASE_URL=postgresql://jobagent:yourpassword@VM_INTERNAL_IP/jobagent \
  --set-env-vars BUCKET_NAME=$BUCKET_NAME
```

### Step 7 — Set up Cloud Scheduler

```bash
# Trigger scraper at 8am and 6pm daily (America/Chicago — adjust to your timezone)
gcloud scheduler jobs create http scraper-morning \
  --location=$REGION \
  --schedule="0 8 * * *" \
  --uri="https://YOUR_CLOUD_RUN_URL/trigger/scraper" \
  --http-method=POST \
  --time-zone="America/Chicago"

gcloud scheduler jobs create http scraper-evening \
  --location=$REGION \
  --schedule="0 18 * * *" \
  --uri="https://YOUR_CLOUD_RUN_URL/trigger/scraper" \
  --http-method=POST \
  --time-zone="America/Chicago"

# Tracker runs once per day at noon
gcloud scheduler jobs create http tracker-daily \
  --location=$REGION \
  --schedule="0 12 * * *" \
  --uri="https://YOUR_CLOUD_RUN_URL/trigger/tracker" \
  --http-method=POST \
  --time-zone="America/Chicago"
```

### Step 8 — Enable Cloud IAP for secure dashboard access

```bash
# Enable IAP on the Cloud Run service
gcloud iap web enable --resource-type=cloud-run \
  --service=job-agent-dashboard \
  --region=$REGION

# Grant yourself access
gcloud iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service=job-agent-dashboard \
  --region=$REGION \
  --member="user:YOUR_GOOGLE_EMAIL" \
  --role="roles/iap.httpsResourceAccessor"
```

---

## requirements.txt

```
anthropic>=0.25.0
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
```

---

## .env.example (for local development only)

```bash
# Candidate profile
CANDIDATE_LINKEDIN=https://linkedin.com/in/YOUR_HANDLE
CANDIDATE_GITHUB=https://github.com/YOUR_HANDLE
CANDIDATE_PORTFOLIO=https://yourportfolio.com
CANDIDATE_FIRST_NAME=Your
CANDIDATE_LAST_NAME=Name
CANDIDATE_EMAIL=youremail@gmail.com

# Platform credentials
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=
INDEED_EMAIL=
INDEED_PASSWORD=
HANDSHAKE_EMAIL=
HANDSHAKE_PASSWORD=
GLASSDOOR_EMAIL=
GLASSDOOR_PASSWORD=
GREENHOUSE_EMAIL=
GREENHOUSE_PASSWORD=

# APIs
ANTHROPIC_API_KEY=

# Database
DATABASE_URL=postgresql://jobagent:yourpassword@localhost/jobagent

# GCP
GCP_PROJECT_ID=
BUCKET_NAME=
```

---

## Human Review Workflow (Day-to-Day Usage)

```
8:00 AM  → Cloud Scheduler fires → Scraper runs → New jobs appear in DB
           Orchestrator scores + tailors each job automatically

~9:00 AM → You open dashboard (your Cloud IAP URL)
           Queue tab shows new jobs sorted by match score (highest first)

For each job:
  → Click "Review"
  → See: title, company, salary, match score, resume diff, cover letter
  → Edit cover letter if needed (inline text box)
  → Click "Approve" or "Skip"

After approvals:
  → Submitter agent fires for each approved application
  → Playwright fills and submits forms in the background
  → Tracker tab updates with submitted status

7 days later:
  → Tracker agent checks for responses
  → You get an email summary of any updates
  → Follow-up nudges created for no-response applications
```

---

## Key Implementation Notes for Coding Agent

1. **Playwright must run in headless mode on the VM** — set `headless=True` in all browser launches. Install `chromium` system package, not the Playwright-bundled one, to avoid sandboxing issues on Linux.

2. **Secret Manager access from VM** — the VM has `--scopes=cloud-platform` so it can access Secret Manager without extra auth. Use `google-cloud-secret-manager` SDK:
   ```python
   from google.cloud import secretmanager
   def get_secret(name):
       client = secretmanager.SecretManagerServiceClient()
       name = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
       return client.access_secret_version(name=name).payload.data.decode()
   ```

3. **Deduplication** — always check `external_id` before inserting a job. LinkedIn, Indeed, and others re-show the same listings across keyword searches. Use `INSERT ... ON CONFLICT DO NOTHING`.

4. **Rate limiting** — add `await page.wait_for_timeout(2000)` between actions and randomize delays (1500–3500ms) to avoid bot detection. Never hammer a platform with rapid requests.

5. **Workday Gmail aliases** — `youremail+COMPANY@gmail.com` routes to your main inbox. Use the company name or Workday subdomain as the alias tag. Store the alias used in `workday_accounts.email`.

6. **Claude API JSON parsing** — wrap all `json.loads()` calls in try/except. If Claude returns malformed JSON (rare but possible), log the raw response and skip that job rather than crashing the orchestrator.

7. **Cloud Run ↔ VM communication** — Cloud Run cannot directly call code on the VM. The pattern is: Cloud Run writes a job to the `jobs` table with a trigger flag, and the VM polls the DB every 60 seconds for new work. Alternatively, use Cloud Pub/Sub for a cleaner event-driven trigger.

8. **PDF generation for tailored resume** — use `reportlab` or `weasyprint` to generate the tailored PDF from the Claude API output. Keep the same visual template as the base resume; only swap the bullet text.

9. **Local development** — use `docker-compose.yml` with a Postgres container so the full stack runs locally without GCP. Use `.env` file instead of Secret Manager in local mode. Gate on `ENV=local` vs `ENV=production`.

10. **CAPTCHA handling** — some platforms (especially Glassdoor) show CAPTCHAs. The submitter should detect CAPTCHA presence, pause, and send a notification to the dashboard so you can manually solve it. Do not attempt automated CAPTCHA solving.

---

## Estimated Monthly GCP Cost (with free credits)

| Service            | Cost            |
|--------------------|-----------------|
| Compute Engine e2-small | ~$13/mo   |
| Cloud Run          | ~$0 (free tier) |
| Cloud Storage      | ~$0.02/mo       |
| Cloud Scheduler    | $0 (free tier)  |
| Secret Manager     | ~$0.06/mo       |
| Cloud IAP          | $0              |
| **Total**          | **~$13–14/mo**  |

Free credit allocation ($300) covers approximately **20–22 months** of operation.
