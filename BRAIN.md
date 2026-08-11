# Forge Architectural Memory

## Important decisions

- Forge is an AI-native software engineering workspace, not a standalone code-generation tool.
- The product is desktop-first, implemented with Tauri, and is paired with a Next.js web experience.
- FastAPI services and workers provide the backend execution model.
- PostgreSQL is the durable system of record; Redis provides caching and supporting fast-access state.
- Repository indexing, memory, search, and deployment are first-class systems.
- The v2.0 documentation suite is authoritative over v1.0 material. The v1.0 Master Product Vision is a draft whose detailed content was not inserted.

## Design philosophy

- Keep engineering work in context: navigation, workbench, AI intelligence, and activity are cohesive workspace capabilities.
- Treat AI as a validated, repository-aware collaborator with human review at the end of its flow.
- Prefer reusable foundations over one-off UI or prompt behavior.

## Backend conventions

- Organize backend work into FastAPI services and workers within the monorepo.
- Keep domain/schema, lifecycle, caching, security, and production database concerns explicit.
- Use PostgreSQL for persistence and Redis where low-latency cached state is appropriate.
- Design for logs, metrics, alerts, and backups from the outset.
- Decided (Milestone 1): repository port interfaces live in `domain/repositories.py`; SQLAlchemy adapters live in `infrastructure/*_repository.py`; application services in `application/`. Security primitives sit behind `domain/security.py` protocols. The presentation layer contains no SQLAlchemy logic.
- Decided: dependency injection via FastAPI `Depends` chains rooted in `presentation/http/dependencies.py`; one shared DB session factory and one Redis client per app lifespan.
- Decided: audit events are first-class records (`audit_events` table) capturing user, session, ip, user agent, reason, and a JSON payload.
- Decided (Feature Pack 5): repository intelligence indexes through domain ports — `GitClient`, `TreeSitterParser`, `EmbeddingProvider` in the domain, concrete implementations in `infrastructure/` (subprocess git, tree-sitter, embeddings), so application services never touch SQLAlchemy/subprocess/library details. Embeddings default to disabled (`NullEmbedder`); the local sentence-transformers embedder is an optional extra, the dimension is fixed at 384 (`vector(384)`), and search uses exact cosine similarity until real repository volume is measured. Incremental indexing (content-hash + `git diff --name-status`) exists but the sync trigger is intentionally separate and not yet built.
- Decided (Feature Pack 6): the context & memory layer sits between repository intelligence and the future LLM/agent layer. Durable memory is typed (`decision`/`convention`/`fact`/`preference`/`summary`/`annotation`) and scoped (`workspace`/`repository`/`user`); a user-scoped memory is visible only to its owner, enforced at the SQL adapter level, not just the API. The context model is a ranked, deduplicated, truncated `ContextWindow` assembled from memory + repository intelligence (symbols/files/dependencies/chunks) + ephemeral conversation context. Durable vs ephemeral: conversation context lives in Redis (`forge:ctx:{session}:{conversation}`, 100-entry cap, TTL), never auto-promoted to memory. Retrieval combines structural (always) with semantic (only when embeddings enabled) and degrades gracefully otherwise. Ranking weights are configurable via Settings. Invalidation: after a repository index, only memories whose `source_file_path` is in the changed-path set are marked stale; memory failures never fail indexing. Embedding fallback: memory creation succeeds with a NULL vector when embeddings are disabled, and the maintenance worker backfills later. Verified against live PostgreSQL 16 + pgvector 0.8.6 + Redis 7.4 (2026-08-11): 258 tests, Alembic 0006 upgrade/downgrade, ruff clean.

## API conventions

- Expose REST endpoints and WebSockets under `/v1`.
- Include authentication, pagination, consistent errors, SDK strategy, and lifecycle management.
- Decided (Milestone 1): a global envelope for every endpoint. Success: `{"success": true, "data": <payload>, "meta": {}}`. Error: `{"success": false, "error": {"code", "message", "details"}}` with stable machine-readable codes (`authentication_error`, `authorization_error`, `validation_error`, `not_found`, `conflict`, `database_error`, `rate_limit_exceeded`, …).
- Decided: bearer access tokens (JWT, 15 min) carry `sub` and `sid` (session id) claims; the httponly `forge_refresh` cookie on the `/v1/auth` path drives rotation. A revoked or expired server-side session invalidates the access token on the next request.
- Decided: refresh tokens rotate on every use; presenting a consumed token revokes the whole token family (reuse detection).
- Decided: OAuth authorize/callback endpoints use `state` + PKCE (S256) and a nonce for OIDC providers (Google); state/verifier/nonce transiently live in Redis.

## UX principles

- Desktop-first, contextual workspace panels.
- Primary workbench layout: Navigator | Workbench | Intelligence Panel | Activity Dock.
- The component system must be accessible, keyboard-first, responsive, and theme-aware.
- Major planned surfaces include landing, login, workspace picker, workbench, search, settings, and deployments.

## Lessons learned

- Documentation includes several high-level placeholder documents. Do not turn their headings into unsupported implementation details.
- The v1.0 suite is an index/reference package; v2.0 documents hold the concrete available decisions.

## Do not forget

- AI changes require user approval before application.
- AI outputs must be validated and identify affected files.
- Prompt design must remain concise, deterministic, repository-aware, and use structured outputs.
- Critical flows require testing before release, including AI evaluation.
