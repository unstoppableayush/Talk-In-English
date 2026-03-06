from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.middleware import (
    RateLimitMiddleware,
    RequestIdMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.api import auth, sessions, rooms, evaluations, progress, section_tests, leaderboard, roleplay
from app.ws import router as ws_router
from app.ws.connection_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    setup_logging()
    if settings.REDIS_URL:
        await manager.enable_redis(settings.REDIS_URL)
    yield
    # ── Shutdown ──────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title="Speaking App API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.ENVIRONMENT == "development" else None,
        redoc_url="/api/redoc" if settings.ENVIRONMENT == "development" else None,
    )

    # ── Middleware (outermost → innermost) ─────────────────────
    # 1. Request ID — must be outermost so every layer can read it
    app.add_middleware(RequestIdMiddleware)
    # 2. Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    # 3. Request logging (uses request_id set by above)
    app.add_middleware(RequestLoggingMiddleware)
    # 4. Rate limiting (100 reqs/min per IP)
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
    # 5. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── REST routers ──────────────────────────────────────────
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
    app.include_router(rooms.router, prefix="/api/v1/rooms", tags=["rooms"])
    app.include_router(evaluations.router, prefix="/api/v1/eval", tags=["evaluations"])
    app.include_router(progress.router, prefix="/api/v1/progress", tags=["progress"])
    app.include_router(section_tests.router, prefix="/api/v1/tests", tags=["section-tests"])
    app.include_router(leaderboard.router, prefix="/api/v1/leaderboard", tags=["leaderboard"])
    app.include_router(roleplay.router, prefix="/api/v1/roleplay", tags=["roleplay"])

    # ── WebSocket router ──────────────────────────────────────
    app.include_router(ws_router, prefix="/ws", tags=["websocket"])

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()
