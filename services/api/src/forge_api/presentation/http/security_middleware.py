from collections import defaultdict, deque
from time import monotonic
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response=await call_next(request)
        response.headers.update({"Content-Security-Policy":"default-src 'self'; frame-ancestors 'none'","Strict-Transport-Security":"max-age=31536000; includeSubDomains","X-Frame-Options":"DENY","X-Content-Type-Options":"nosniff","Referrer-Policy":"strict-origin-when-cross-origin","Permissions-Policy":"camera=(), microphone=(), geolocation=()"})
        return response
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int=20, window: int=60): super().__init__(app); self.limit=limit; self.window=window; self.hits=defaultdict(deque)
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/v1/auth"):
            key=request.client.host if request.client else "unknown"; now=monotonic(); bucket=self.hits[key]
            while bucket and bucket[0] <= now-self.window: bucket.popleft()
            if len(bucket)>=self.limit: return JSONResponse({"detail":"rate limit exceeded"},status_code=429)
            bucket.append(now)
        return await call_next(request)
