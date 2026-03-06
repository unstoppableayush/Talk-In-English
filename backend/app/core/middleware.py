"""
Production middleware stack for the Speaking App.

Includes:
- Request ID injection (X-Request-ID)
- Security headers (XSS, content-type sniffing, frame options)
- Rate limiting (in-memory token-bucket, per IP)
- Request/Response logging
"""

import logging
import time
import uuid
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("speaking_app.middleware")


# ── 1. Request ID ──────────────────────────────────────────────

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique X-Request-ID to every request/response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── 2. Security Headers ───────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
        return response


# ── 3. Rate Limiter (in-memory, per-IP token bucket) ──────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple per-IP rate limiter using a token-bucket algorithm.
    For production with multiple workers, swap to Redis-backed sliding window.
    """

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for WebSocket upgrades and health checks
        if request.url.path.startswith("/ws") or request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window_seconds

        # Purge expired timestamps
        bucket = self._buckets[client_ip]
        self._buckets[client_ip] = [t for t in bucket if t > cutoff]

        if len(self._buckets[client_ip]) >= self.max_requests:
            remaining = 0
            retry_after = int(self._buckets[client_ip][0] + self.window_seconds - now) + 1
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        self._buckets[client_ip].append(now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            self.max_requests - len(self._buckets[client_ip])
        )
        return response


# ── 4. Request Logging ─────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code and elapsed time for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s -> %d (%.1fms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response
