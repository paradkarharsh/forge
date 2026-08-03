"""HTTP security middleware: security headers and rate limiting."""
from collections import defaultdict, deque
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from forge_api.presentation.http.contracts import ErrorPayload


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply hardened security headers to every response."""

    _HEADERS = {
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.update(self._HEADERS)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window in-memory rate limit for authentication endpoints."""

    def __init__(self, app, limit: int = 20, window: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def _rate_limited(self) -> JSONResponse:
        payload = ErrorPayload(
            code="rate_limit_exceeded",
            message="Too many requests, please slow down",
        )
        return JSONResponse(
            status_code=429,
            content={"success": False, "error": payload.model_dump()},
        )

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/v1/auth"):
            key = request.client.host if request.client else "unknown"
            now = monotonic()
            bucket = self.hits[key]
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return self._rate_limited()
            bucket.append(now)
        return await call_next(request)
