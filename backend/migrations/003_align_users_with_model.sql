-- Align auth.users table with the SQLAlchemy User model
-- Renames columns and adds missing ones

-- Rename username → display_name
ALTER TABLE auth.users RENAME COLUMN username TO display_name;

-- Rename hashed_password → password_hash
ALTER TABLE auth.users RENAME COLUMN hashed_password TO password_hash;

-- Rename full_name → (drop, not in model)
ALTER TABLE auth.users DROP COLUMN IF EXISTS full_name;

-- Drop is_verified (not in model)
ALTER TABLE auth.users DROP COLUMN IF EXISTS is_verified;

-- Add missing columns
ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';
ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS level VARCHAR(20) NOT NULL DEFAULT 'beginner';

-- Change display_name to allow non-unique (model has no unique constraint on it)
ALTER TABLE auth.users DROP CONSTRAINT IF EXISTS users_username_key;
