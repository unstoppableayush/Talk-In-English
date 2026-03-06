-- Add Google OAuth columns to auth.users
-- Run this manually if you have an existing database

ALTER TABLE auth.users
    ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE,
    ALTER COLUMN hashed_password DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_google_id ON auth.users (google_id) WHERE google_id IS NOT NULL;
