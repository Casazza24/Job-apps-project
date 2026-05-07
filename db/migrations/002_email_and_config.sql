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
