"""FastAPI application factory.

Assembles middleware, exception handlers, routers, and a lifespan that
creates shared infrastructure (database session factory, cache client) and
runs session cleanup on a background interval.
"""
import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from forge_api.infrastructure.cache import create_cache_client
from forge_api.infrastructure.database import create_session_factory
from forge_api.infrastructure.settings import Settings, get_settings
from forge_api.presentation.http.auth import router as auth_router
from forge_api.presentation.http.errors import register_exception_handlers
from forge_api.presentation.http.health import router as health_router
from forge_api.presentation.http.llm import (
    conversation_router,
    llm_router,
    usage_router,
)
from forge_api.presentation.http.memory import (
    context_router,
    memory_router,
)
from forge_api.presentation.http.oauth import router as oauth_router
from forge_api.presentation.http.repository import router as repository_router
from forge_api.presentation.http.security_middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from forge_api.presentation.http.sessions import router as sessions_router
from forge_api.presentation.http.workspaces import router as workspace_router

logger = logging.getLogger(__name__)


async def _session_cleanup_loop(interval: int, settings: Settings) -> None:
    """Periodically clean up expired sessions."""
    from forge_api.application.auth.session_service import SessionService
    from forge_api.infrastructure.audit import AuditLogger
    from forge_api.infrastructure.security import (
        JwtTokenProvider,
        SecureRefreshTokenGenerator,
    )
    from forge_api.infrastructure.session_repository import SqlSessionRepository

    factory = create_session_factory(settings)

    while True:
        await asyncio.sleep(interval)
        try:
            async with factory() as db:
                svc = SessionService(
                    sessions=SqlSessionRepository(db),
                    tokens=JwtTokenProvider(settings),
                    refresh=SecureRefreshTokenGenerator(),
                    audit=AuditLogger(db),
                    refresh_ttl_days=settings.refresh_token_ttl_days,
                    last_active_throttle_seconds=settings.session_last_active_throttle_seconds,
                )
                count = await svc.cleanup_expired()
                await db.commit()
                if count:
                    logger.info("Cleaned up %d expired sessions", count)
        except Exception:
            logger.exception("Session cleanup failed")


async def _index_worker_loop(settings: Settings) -> None:
    """Run the background repository index worker."""
    from forge_api.application.indexing.index_worker import IndexWorker
    from forge_api.presentation.http.dependencies import create_index_services

    worker = IndexWorker(
        session_factory=create_session_factory(settings),
        create_services=create_index_services,
        poll_seconds=settings.index_worker_poll_seconds,
    )
    await worker.run()


async def _memory_maintenance_loop(settings: Settings) -> None:
    """Run the background memory maintenance worker."""
    from forge_api.application.memory.memory_worker import MemoryMaintenanceWorker
    from forge_api.presentation.http.dependencies import (
        create_memory_maintenance_services,
    )

    worker = MemoryMaintenanceWorker(
        session_factory=create_session_factory(settings),
        create_services=create_memory_maintenance_services,
        poll_seconds=settings.memory_maintenance_interval_seconds,
    )
    await worker.run()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    # Shared database session factory and cache client.
    engine = create_session_factory(settings)
    app.state.session_factory = engine

    cache = None
    try:
        client = create_cache_client(settings)
        await client.ping()
        cache = client
    except Exception:
        logger.warning("Cache unavailable; OAuth flows will be disabled")
    app.state.cache = cache

    tasks = [
        asyncio.create_task(
            _session_cleanup_loop(settings.session_cleanup_interval_seconds, settings)
        )
    ]
    if settings.index_worker_enabled:
        tasks.append(asyncio.create_task(_index_worker_loop(settings)))
    if settings.memory_maintenance_worker_enabled:
        tasks.append(asyncio.create_task(_memory_maintenance_loop(settings)))

    yield

    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    if cache is not None:
        await cache.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Forge API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Middleware (applied in reverse order of addition)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/v1")
    app.include_router(workspace_router, prefix="/v1")
    app.include_router(repository_router, prefix="/v1")
    app.include_router(memory_router, prefix="/v1")
    app.include_router(context_router, prefix="/v1")
    app.include_router(llm_router, prefix="/v1")
    app.include_router(conversation_router, prefix="/v1")
    app.include_router(usage_router, prefix="/v1")
    app.include_router(oauth_router, prefix="/v1")
    app.include_router(sessions_router, prefix="/v1")

    return app
