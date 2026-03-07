import asyncio
from sqlalchemy import text
from app.core.database import engine

SQL = """
CREATE TABLE IF NOT EXISTS public.app_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    display_name    VARCHAR(100) NOT NULL,
    password_hash   VARCHAR(255),
    google_id       VARCHAR(255) UNIQUE,
    avatar_url      VARCHAR(500),
    native_language VARCHAR(10),
    target_language VARCHAR(10)  NOT NULL DEFAULT 'en',
    role            VARCHAR(20)  NOT NULL DEFAULT 'user',
    level           VARCHAR(20)  NOT NULL DEFAULT 'beginner',
    xp              INTEGER      NOT NULL DEFAULT 0,
    streak_days     INTEGER      NOT NULL DEFAULT 0,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_users_email     ON public.app_users (email);
CREATE INDEX IF NOT EXISTS idx_app_users_google_id ON public.app_users (google_id) WHERE google_id IS NOT NULL;
"""

async def run():
    async with engine.begin() as conn:
        for stmt in SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                print(f"Running: {stmt[:70]}...")
                await conn.execute(text(stmt))
    print("Done — public.app_users created!")

asyncio.run(run())
