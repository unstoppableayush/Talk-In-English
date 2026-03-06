-- Initialize PostgreSQL schemas for the Speaking App
-- Run automatically on first docker-compose up

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS sessions;
CREATE SCHEMA IF NOT EXISTS eval;
CREATE SCHEMA IF NOT EXISTS ai;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
