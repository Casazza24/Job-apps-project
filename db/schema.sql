-- schema.sql
-- Run: psql -U jobagent -d jobagent -f db/schema.sql

CREATE TABLE IF NOT EXISTS jobs (
    id              SERIAL PRIMARY KEY,
    external_id     TEXT UNIQUE NOT NULL,
    platform        TEXT NOT NULL,
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    salary_range    TEXT,
    url             TEXT NOT NULL,
    description     TEXT,
    match_score     INTEGER,
    score_reasoning TEXT,
    status          TEXT DEFAULT 'new',
    is_workday      BOOLEAN DEFAULT FALSE,
    workday_url     TEXT,
    scraped_at      TIMESTAMP DEFAULT NOW(),
    reviewed_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    id                  SERIAL PRIMARY KEY,
    job_id              INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    tailored_resume_url TEXT,
    cover_letter_url    TEXT,
    cover_letter_text   TEXT,
    resume_diff         JSONB,
    status              TEXT DEFAULT 'pending_review',
    submitted_at        TIMESTAMP,
    last_checked_at     TIMESTAMP,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workday_accounts (
    id              SERIAL PRIMARY KEY,
    employer_domain TEXT UNIQUE NOT NULL,
    email           TEXT NOT NULL,
    password_ref    TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id              SERIAL PRIMARY KEY,
    application_id  INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    scheduled_at    TIMESTAMP,
    sent_at         TIMESTAMP,
    type            TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform);
CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON jobs(match_score DESC);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
