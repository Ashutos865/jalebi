"""Production middleware: rate limiting, security headers, request logging."""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("jalebi.request")


def _client_ip(request: Request) -> str:
    # Trust the first X-Forwarded-For hop when behind a reverse proxy.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP limiter on /api/* (excludes /api/health). In-memory, so
    each worker has its own counter — fine for basic abuse protection; use a shared
    store (Redis) if you need strict global limits across many workers."""

    def __init__(self, app, limit_per_min: int):
        super().__init__(app)
        self.limit = limit_per_min
        self._hits: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self.limit <= 0 or not path.startswith("/api/") or path == "/api/health":
            return await call_next(request)

        window = int(time.time() // 60)
        key = f"{_client_ip(request)}:{window}"
        with self._lock:
            w, count = self._hits[key]
            if w != window:
                count = 0
            count += 1
            self._hits[key] = (window, count)
            # Opportunistic cleanup of old windows.
            if len(self._hits) > 10000:
                self._hits = {k: v for k, v in self._hits.items() if v[0] >= window - 1}

        if count > self.limit:
            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again shortly."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        resp = await call_next(request)
        resp.headers["X-RateLimit-Limit"] = str(self.limit)
        resp.headers["X-RateLimit-Remaining"] = str(max(0, self.limit - count))
        return resp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp: Response = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-XSS-Protection", "0")
        resp.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        return resp


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            resp = await call_next(request)
        except Exception:
            logger.exception("req=%s %s %s -> 500", rid, request.method, request.url.path)
            raise
        ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "req=%s %s %s -> %s %dms ip=%s",
            rid, request.method, request.url.path, resp.status_code, ms,
            _client_ip(request),
        )
        resp.headers["X-Request-ID"] = rid
        return resp
