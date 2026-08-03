from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from forge_api.presentation.http.security_middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from forge_api.presentation.http.health import router as health_router
from forge_api.presentation.http.auth import router as auth_router
from forge_api.presentation.http.workspaces import router as workspace_router
from forge_api.presentation.http.oauth import router as oauth_router
from forge_api.presentation.http.sessions import router as sessions_router
def create_app() -> FastAPI:
    app = FastAPI(title="Forge API", version="0.1.0", docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost","127.0.0.1"])
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True, allow_methods=["GET","POST","PATCH","DELETE"], allow_headers=["Authorization","Content-Type","X-CSRF-Token"])
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/v1")
    app.include_router(workspace_router, prefix="/v1")
    app.include_router(oauth_router, prefix="/v1")
    app.include_router(sessions_router, prefix="/v1")
    return app
