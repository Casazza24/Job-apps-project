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
    token_json  TEXT NOT NULL,  -- token_json stores the full OAuth2 credential JSON from google-auth. Application layer must never log this value. Consider app-layer encryption if DB backups are unencrypted.
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Key/value config store (keywords, domains, etc.)
CREATE TABLE IF NOT EXISTS search_config (
    id          SERIAL PRIMARY KEY,
    key         TEXT UNIQUE NOT NULL,
    value_json  JSONB NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_applications_sender_domain ON applications(sender_domain);

-- Auto-update trigger for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_gmail_tokens_updated_at
    BEFORE UPDATE ON gmail_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_search_config_updated_at
    BEFORE UPDATE ON search_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
