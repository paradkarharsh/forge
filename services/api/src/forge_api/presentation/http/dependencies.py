"""Dependency injection for the presentation layer.

Application services are assembled through ``Depends()`` chains rooted here.
Database session factory and cache client are created once at application
startup (lifespan) and shared via ``app.state``; every request builds fresh
repositories and services bound to the shared session factory.
"""
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from forge_api.application.auth.auth_service import AuthService
from forge_api.application.auth.oauth_service import OAuthService
from forge_api.application.auth.session_service import SessionService
from forge_api.application.indexing.chunking_service import ChunkingService
from forge_api.application.indexing.dependency_resolver import DependencyResolver
from forge_api.application.indexing.file_discovery_service import FileDiscoveryService
from forge_api.application.indexing.index_service import RepositoryIndexService
from forge_api.application.indexing.search_service import SearchService
from forge_api.application.memory.context_assembly_service import ContextAssemblyService
from forge_api.application.memory.maintenance_service import MemoryMaintenanceService
from forge_api.application.memory.memory_service import MemoryService
from forge_api.application.repositories.background_jobs import BackgroundJobService
from forge_api.application.repositories.clone_service import RepositoryCloneService
from forge_api.application.repositories.import_service import RepositoryImportService
from forge_api.application.repositories.repository_service import RepositoryService
from forge_api.application.workspaces.workspace_service import WorkspaceService
from forge_api.domain.errors import AuthenticationError, ServiceUnavailableError
from forge_api.domain.indexing import IndexingConfig
from forge_api.domain.memory import ContextRankingConfig
from forge_api.domain.security import AccessClaims
from forge_api.infrastructure.audit import AuditLogger
from forge_api.infrastructure.conversation_context import (
    NullConversationContextStore,
    RedisConversationContextStore,
)
from forge_api.infrastructure.database import create_session_factory
from forge_api.infrastructure.embedding import build_embedding_provider
from forge_api.infrastructure.git import SubprocessGitClient
from forge_api.infrastructure.memory_repository import SqlMemoryRepository
from forge_api.infrastructure.oauth import OAuthStateManager
from forge_api.infrastructure.oauth_identity_repository import (
    SqlOAuthIdentityRepository,
)
from forge_api.infrastructure.repository_branch_repository import (
    SqlRepositoryBranchRepository,
)
from forge_api.infrastructure.repository_chunk_repository import (
    SqlRepositoryChunkRepository,
)
from forge_api.infrastructure.repository_dependency_repository import (
    SqlRepositoryDependencyRepository,
)
from forge_api.infrastructure.repository_event_repository import (
    SqlRepositoryEventRepository,
)
from forge_api.infrastructure.repository_file_repository import (
    SqlRepositoryFileRepository,
)
from forge_api.infrastructure.repository_repository import SqlRepositoryRepository
from forge_api.infrastructure.repository_symbol_repository import (
    SqlRepositorySymbolRepository,
)
from forge_api.infrastructure.repository_sync_job_repository import (
    SqlRepositorySyncJobRepository,
)
from forge_api.infrastructure.security import (
    Argon2PasswordHasher,
    JwtTokenProvider,
    SecureRefreshTokenGenerator,
)
from forge_api.infrastructure.session_repository import SqlSessionRepository
from forge_api.infrastructure.settings import Settings, get_settings
from forge_api.infrastructure.treesitter import ForgeTreeSitterParser
from forge_api.infrastructure.user_repository import SqlUserRepository
from forge_api.infrastructure.workspace_repository import SqlWorkspaceRepository

_bearer = HTTPBearer()


# ─── Singletons / settings ─────────────────────────────────────────


def _token_provider(settings: Settings = Depends(get_settings)) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


def _password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


def _refresh_generator() -> SecureRefreshTokenGenerator:
    return SecureRefreshTokenGenerator()


# ─── App-shared session factory / cache ────────────────────────────


def _session_factory(request: Request) -> async_sessionmaker:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        factory = create_session_factory(get_settings())
    return factory


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory(request)() as session:
        yield session
        await session.commit()


def get_cache(request: Request) -> Redis:
    cache = getattr(request.app.state, "cache", None)
    if cache is None:
        raise ServiceUnavailableError("Cache is unavailable")
    return cache


# ─── Audit ──────────────────────────────────────────────────────────


def get_audit(db: AsyncSession = Depends(get_session)) -> AuditLogger:
    return AuditLogger(db)


# ─── Authentication ─────────────────────────────────────────────────


def current_claims(
    token: HTTPAuthorizationCredentials = Depends(_bearer),
    tokens: JwtTokenProvider = Depends(_token_provider),
) -> AccessClaims:
    """Decode the bearer token and return the access claims."""
    try:
        return tokens.decode_access_token(token.credentials)
    except Exception as exc:
        raise AuthenticationError("Invalid access token") from exc


async def validated_claims(
    claims: AccessClaims = Depends(current_claims),
    db: AsyncSession = Depends(get_session),
) -> AccessClaims:
    """Decode the bearer token AND verify the session is still active."""
    from datetime import UTC, datetime

    from forge_api.infrastructure.session_repository import SqlSessionRepository

    repo = SqlSessionRepository(db)
    session = await repo.get(claims.session_id, user_id=claims.user_id)
    if not session or session.revoked_at is not None:
        raise AuthenticationError("Session has been revoked")
    if session.expires_at < datetime.now(UTC):
        raise AuthenticationError("Session has expired")
    return claims


def current_user_id(claims: AccessClaims = Depends(current_claims)) -> str:
    """Convenience: return user_id as a string for backward compat."""
    return str(claims.user_id)


# ─── Application services ──────────────────────────────────────────


def get_auth_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    tokens: JwtTokenProvider = Depends(_token_provider),
    passwords: Argon2PasswordHasher = Depends(_password_hasher),
    refresh: SecureRefreshTokenGenerator = Depends(_refresh_generator),
    audit: AuditLogger = Depends(get_audit),
) -> AuthService:
    return AuthService(
        users=SqlUserRepository(db),
        sessions=SqlSessionRepository(db),
        tokens=tokens,
        passwords=passwords,
        refresh=refresh,
        audit=audit,
        refresh_ttl_days=settings.refresh_token_ttl_days,
    )


def get_session_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    tokens: JwtTokenProvider = Depends(_token_provider),
    refresh: SecureRefreshTokenGenerator = Depends(_refresh_generator),
    audit: AuditLogger = Depends(get_audit),
) -> SessionService:
    return SessionService(
        sessions=SqlSessionRepository(db),
        tokens=tokens,
        refresh=refresh,
        audit=audit,
        refresh_ttl_days=settings.refresh_token_ttl_days,
        last_active_throttle_seconds=settings.session_last_active_throttle_seconds,
    )


def get_oauth_service(
    db: AsyncSession = Depends(get_session),
    cache: Redis = Depends(get_cache),
    settings: Settings = Depends(get_settings),
    tokens: JwtTokenProvider = Depends(_token_provider),
    refresh: SecureRefreshTokenGenerator = Depends(_refresh_generator),
    audit: AuditLogger = Depends(get_audit),
) -> OAuthService:
    return OAuthService(
        users=SqlUserRepository(db),
        oauth_identities=SqlOAuthIdentityRepository(db),
        sessions=SqlSessionRepository(db),
        tokens=tokens,
        refresh=refresh,
        audit=audit,
        state_manager=OAuthStateManager(cache, settings),
        settings=settings,
    )


def get_workspace_service(
    db: AsyncSession = Depends(get_session),
    audit: AuditLogger = Depends(get_audit),
) -> WorkspaceService:
    return WorkspaceService(
        workspaces=SqlWorkspaceRepository(db),
        audit=audit,
    )


def get_repository_service(
    db: AsyncSession = Depends(get_session),
    audit: AuditLogger = Depends(get_audit),
) -> RepositoryService:
    return RepositoryService(
        repositories=SqlRepositoryRepository(db),
        workspaces=SqlWorkspaceRepository(db),
        events=SqlRepositoryEventRepository(db),
        audit=audit,
    )


def get_import_service(
    db: AsyncSession = Depends(get_session),
    audit: AuditLogger = Depends(get_audit),
) -> RepositoryImportService:
    return RepositoryImportService(
        repositories=SqlRepositoryRepository(db),
        workspaces=SqlWorkspaceRepository(db),
        events=SqlRepositoryEventRepository(db),
        audit=audit,
    )


def get_clone_service(
    db: AsyncSession = Depends(get_session),
    audit: AuditLogger = Depends(get_audit),
) -> RepositoryCloneService:
    return RepositoryCloneService(
        repositories=SqlRepositoryRepository(db),
        branches=SqlRepositoryBranchRepository(db),
        workspaces=SqlWorkspaceRepository(db),
        events=SqlRepositoryEventRepository(db),
        audit=audit,
    )


def get_background_job_service(
    db: AsyncSession = Depends(get_session),
) -> BackgroundJobService:
    return BackgroundJobService(
        repositories=SqlRepositoryRepository(db),
        sync_jobs=SqlRepositorySyncJobRepository(db),
    )


def get_branch_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlRepositoryBranchRepository:
    return SqlRepositoryBranchRepository(db)


# ─── Repository intelligence ─────────────────────────────────────────


def _indexing_config(settings: Settings) -> IndexingConfig:
    return IndexingConfig(
        max_file_bytes=settings.index_max_file_bytes,
        max_files=settings.index_max_files,
        chunk_tokens=settings.index_chunk_tokens,
        chunk_overlap=settings.index_chunk_overlap,
        embedding_batch_size=settings.index_embedding_batch_size,
        timeout_seconds=settings.index_timeout_seconds,
    )


def _build_index_service(
    db: AsyncSession, settings: Settings, audit: AuditLogger
) -> RepositoryIndexService:
    git = SubprocessGitClient(timeout_seconds=settings.index_git_timeout_seconds)
    discovery = FileDiscoveryService(git=git, max_files=settings.index_max_files)
    return RepositoryIndexService(
        repositories=SqlRepositoryRepository(db),
        files=SqlRepositoryFileRepository(db),
        symbols=SqlRepositorySymbolRepository(db),
        dependencies=SqlRepositoryDependencyRepository(db),
        chunks=SqlRepositoryChunkRepository(db),
        events=SqlRepositoryEventRepository(db),
        workspaces=SqlWorkspaceRepository(db),
        git=git,
        parser=ForgeTreeSitterParser(),
        embedding=build_embedding_provider(
            settings.embedding_provider, settings.embedding_model
        ),
        chunker=ChunkingService(),
        resolver=DependencyResolver(),
        discovery=discovery,
        config=_indexing_config(settings),
        audit=audit,
        memories=SqlMemoryRepository(db),
    )


def get_index_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    audit: AuditLogger = Depends(get_audit),
) -> RepositoryIndexService:
    return _build_index_service(db, settings, audit)


def get_search_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SearchService:
    return SearchService(
        repositories=SqlRepositoryRepository(db),
        files=SqlRepositoryFileRepository(db),
        symbols=SqlRepositorySymbolRepository(db),
        dependencies=SqlRepositoryDependencyRepository(db),
        chunks=SqlRepositoryChunkRepository(db),
        workspaces=SqlWorkspaceRepository(db),
        embedding=build_embedding_provider(
            settings.embedding_provider, settings.embedding_model
        ),
    )


def create_index_services(
    db: AsyncSession,
) -> tuple[RepositoryIndexService, BackgroundJobService]:
    """Build the index service + background job service for a session.

    Used by the background index worker, which manages its own sessions
    rather than going through request-scoped dependencies.
    """
    settings = get_settings()
    audit = AuditLogger(db)
    index_service = _build_index_service(db, settings, audit)
    jobs = BackgroundJobService(
        repositories=SqlRepositoryRepository(db),
        sync_jobs=SqlRepositorySyncJobRepository(db),
    )
    return index_service, jobs


# ─── Context and memory engine ───────────────────────────────────────


def get_memory_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    audit: AuditLogger = Depends(get_audit),
) -> MemoryService:
    return MemoryService(
        memories=SqlMemoryRepository(db),
        workspaces=SqlWorkspaceRepository(db),
        embedding=build_embedding_provider(
            settings.embedding_provider, settings.embedding_model
        ),
        audit=audit,
        max_content_length=settings.memory_max_content_length,
        max_tags=settings.memory_max_tags,
    )


def get_conversation_context_store(
    cache: Redis = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> RedisConversationContextStore:
    return RedisConversationContextStore(
        cache,
        max_entries=settings.context_conversation_max_entries,
        default_ttl_seconds=settings.context_conversation_ttl_seconds,
    )


def get_context_assembly_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    cache: Redis = Depends(get_cache),
    audit: AuditLogger = Depends(get_audit),
) -> ContextAssemblyService:
    return ContextAssemblyService(
        memories=SqlMemoryRepository(db),
        search=get_search_service(db, settings),
        conversation=_conversation_store(cache, settings),
        embedding=build_embedding_provider(
            settings.embedding_provider, settings.embedding_model
        ),
        workspaces=SqlWorkspaceRepository(db),
        audit=audit,
        ranking=ContextRankingConfig(
            semantic_weight=settings.context_rank_semantic_weight,
            recency_weight=settings.context_rank_recency_weight,
            confidence_weight=settings.context_rank_confidence_weight,
            scope_weight=settings.context_rank_scope_weight,
            type_weight=settings.context_rank_type_weight,
        ),
        max_tokens=settings.context_max_tokens,
        min_relevance=settings.context_min_relevance,
        conversation_max_entries=settings.context_conversation_max_entries,
    )


def _conversation_store(
    cache: Redis, settings: Settings,
) -> RedisConversationContextStore | NullConversationContextStore:
    """Build the conversation store, falling back to a no-op when Redis is down.

    Context assembly must gracefully omit conversation context rather than
    crash the entire request when the cache is unavailable.
    """
    if cache is None:
        return NullConversationContextStore()
    return RedisConversationContextStore(
        cache,
        max_entries=settings.context_conversation_max_entries,
        default_ttl_seconds=settings.context_conversation_ttl_seconds,
    )


def create_memory_maintenance_services(
    db: AsyncSession,
) -> MemoryMaintenanceService:
    """Build the memory maintenance service for a session.

    Used by the background memory maintenance worker, which manages its
    own sessions rather than going through request-scoped dependencies.
    """
    settings = get_settings()
    return MemoryMaintenanceService(
        memories=SqlMemoryRepository(db),
        embedding=build_embedding_provider(
            settings.embedding_provider, settings.embedding_model
        ),
        backfill_batch_size=settings.memory_embedding_backfill_batch_size,
    )


# ─── Request context helpers ────────────────────────────────────────


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def client_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def client_device_name(request: Request) -> str | None:
    return request.headers.get("sec-ch-ua-platform")
