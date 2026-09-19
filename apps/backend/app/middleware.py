"""Production middleware: rate limiting, security headers, request logging."""
from __future__ import annotations

import ipaddress
import logging
import time
import uuid
from threading import Lock

from app.config import settings

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("jalebi.request")


def _peer_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_trusted_proxy(peer: str) -> bool:
    """Is the direct peer a proxy we configured?

    Empty trusted-proxy list means "no proxy", which is the safe default for a
    directly-exposed server.
    """
    if not settings.trusted_proxies:
        return False
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for entry in settings.trusted_proxies:
        try:
            if addr in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def _client_ip(request: Request) -> str:
    """The client's address, honouring X-Forwarded-For only behind a proxy.

    X-Forwarded-For is attacker-controlled on a directly-exposed server: anyone
    can rotate it to mint a fresh rate-limit bucket per request, which defeats
    the only abuse control on the expensive /api/evaluate path (and used to be a
    way to blow up the limiter's own memory). It is therefore honoured only when
    the direct peer is in JALEBI_TRUSTED_PROXIES.
    """
    peer = _peer_ip(request)
    if not _is_trusted_proxy(peer):
        return peer
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return peer


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP limiter on /api/* (excludes /api/health). In-memory, so
    each worker has its own counter — fine for basic abuse protection; use a shared
    store (Redis) if you need strict global limits across many workers."""

    def __init__(self, app, limit_per_min: int):
        super().__init__(app)
        self.limit = limit_per_min
        # Plain dict + .get() rather than a defaultdict: the cleanup below rebuilds
        # this mapping, and a comprehension cannot preserve a defaultdict factory.
        self._hits: dict[str, tuple[int, int]] = {}
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self.limit <= 0 or not path.startswith("/api/") or path == "/api/health":
            return await call_next(request)

        window = int(time.time() // 60)
        key = f"{_client_ip(request)}:{window}"
        with self._lock:
            # The window is part of the key, so a miss is always a fresh window.
            _, count = self._hits.get(key, (window, 0))
            count += 1
            self._hits[key] = (window, count)
            # Opportunistic cleanup: drop every key from an elapsed window. Keeping
            # `>= window` (not `window - 1`) means this actually sheds entries under
            # load instead of re-running an O(n) rebuild on every request.
            if len(self._hits) > 10000:
                self._hits = {k: v for k, v in self._hits.items() if v[0] >= window}

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
