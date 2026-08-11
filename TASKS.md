# Forge Tasks

## Completed — Milestone 0

- [x] Initialize pnpm/Turborepo workspace.
- [x] Add Next.js 15, React 19, TypeScript, Tailwind CSS v4, and shadcn/ui configuration.
- [x] Add Tauri 2 desktop shell configuration.
- [x] Add FastAPI service foundation using Clean Architecture.
- [x] Provision PostgreSQL with pgvector and Redis through Docker Compose.
- [x] Add shared type, design-token, UI, and configuration packages.
- [x] Add formatting, linting, commit hooks, CI, environment examples, and developer setup documentation.

## Completed — Milestone 1 (authentication & workspace foundation)

- [x] Approve authentication and workspace architecture.
- [x] Define the global response contract (success/error envelopes) and centralized exception handlers.
- [x] Implement GitHub and Google OAuth provider flow with state, PKCE, and nonce.
- [x] Implement session lifecycle: refresh rotation, reuse detection, revocation, expiration cleanup, `last_active` throttling.
- [x] Implement the audit system (session id, ip, user agent, reason, structured payload).
- [x] Introduce repository interfaces, SQLAlchemy adapters, application services, and dependency injection; remove SQLAlchemy from the presentation layer.
- [x] Add Alembic runtime and follow-up migration for audit_events, oauth_identities, and session context fields.
- [x] Add unit tests for sessions, refresh rotation, reuse detection, authorization, response contracts, exception handlers, audit, and security.
- [x] Add integration tests (gated on live PostgreSQL/Redis) for the end-to-end auth/session flow.

## Completed — Infrastructure Validation (2026-08-04)

- [x] Verify Docker Compose services: PostgreSQL 16 + pgvector 0.8.6 and Redis 7.4 healthy.
- [x] Run Alembic migrations `0001`→`0003` against live PostgreSQL; verify schema.
- [x] Run the full test suite (80 unit + integration) against live infrastructure; 121 tests passing.
- [x] Fix missing database commit in request-scoped session dependency.
- [x] Add `validated_claims` dependency enforcing session revocation/expiry on protected endpoints.

## Completed — Milestone 2 (workspace tenancy)

- [x] Add workspace `slug` (unique, indexed) and `description` columns via migration `0003`.
- [x] Implement workspace CRUD: create (auto/explicit slug), list, get by id, get by slug, partial update, owner-only soft delete.
- [x] Implement membership management: list, add, remove, change role (with role-based authorization and owner protections).
- [x] Add slug generation + validation and uniqueness enforcement with stable error codes.
- [x] Extend audit event types for workspace/member operations.
- [x] Add workspace tenancy unit tests (slugify, CRUD, membership, authorization).
- [x] Add workspace tenancy integration tests (CRUD + membership end-to-end against Postgres).
- [x] Scope protected endpoints through `validated_claims` (session revocation/expiry enforcement).
- [x] Full suite green (121 tests) and ruff clean on all changed files.

## Planned — Future milestones

- [ ] Select and document the first user-facing vertical slice.
- [ ] Implement workspace invites and membership UX.
- [ ] Implement repository indexer, memory engine, search, and deployment services.
- [ ] Define Forge Frame design tokens and component specifications in detail.
- [ ] Define authentication architecture and threat model.

## Completed — Feature Pack 4 (Repository Onboarding, 2026-08-04)

- [x] Repository domain: `RepositoryRecord`, `BranchRecord`, `SyncJobRecord`, `RepositoryEventRecord`; enums for provider (github/gitlab/bitbucket/local), visibility, clone status, sync status, sync job type/status.
- [x] Database migration `0004_repository_onboarding`: `repositories`, `repository_branches`, `repository_sync_jobs`, `repository_events` tables with UUID PKs, workspace FK (CASCADE), indexes, and JSON payloads.
- [x] Repository CRUD service: create, list (workspace-scoped), get, update (partial via `model_fields_set`), archive, soft delete, restore — all with workspace RBAC.
- [x] Import service: GitHub URL import (regex-validated) and local-folder import; provider-strategy design leaves room for GitLab/Bitbucket without interface changes.
- [x] Clone service: remote validation via `git ls-remote`, `git clone --no-checkout`, default-branch detection, branch discovery (`git branch -r`), metadata extraction (last commit hash, size), and clone status transitions pending → cloning → ready/failed.
- [x] Background job service: enqueue/start/complete/fail for clone, sync, and index job types; index queue created but not performing indexing yet.
- [x] Audit events: `repository.created`, `repository.imported`, `repository.cloned`, `repository.updated`, `repository.archived`, `repository.restored`, `repository.deleted`; domain `repository_events` log wired into services.
- [x] API router `/v1/repositories`: POST/GET list/GET one/PATCH/DELETE, POST import, POST clone, POST `{id}/archive`, POST `{id}/restore`, GET `{id}/branches`, GET `{id}/status` — all behind `validated_claims` and the global response contract.
- [x] Dependency injection for all repository services via `presentation/http/dependencies.py`.
- [x] Unit tests (CRUD, import, clone, status, background jobs) + integration tests (CRUD lifecycle, import, authorization) against live PostgreSQL.
- [x] ruff clean and full test suite green (121 previous + repository tests).

## Completed — Feature Pack 4 Validation Fixes (2026-08-10)

- [x] Update `test_audit.py` expected-event-set to include all `repository.*` audit event types.
- [x] Add per-test `_reset_rate_limiter` autouse fixture to `test_integration.py` for rate-limiter isolation (production limits unchanged).
- [x] Fix 7 pre-existing ruff lint errors in `alembic/versions/0001_auth_workspace.py` (formatting only, no schema change).
- [x] Full validation: `ruff check .` clean, 163 tests passing, Alembic chain base↔head verified, app startup confirmed.

## Completed — Feature Pack 5 (Repository Intelligence, 2026-08-11)

- [x] Domain (`domain/indexing.py`): FileRecord, SymbolRecord, DependencyRecord, ChunkRecord, IndexStats/Chunk/IndexingConfig, IndexStatus, SymbolKind, DependencyKind enums; path/revision validation helpers; parser/embedding/git ports.
- [x] Migration `0005_repository_intelligence`: `repository_files`, `repository_symbols`, `repository_dependencies`, `repository_chunks` (with `vector(384)`), plus `index_status`/`indexed_at`/`file_count`/`symbol_count` on repositories — reversible.
- [x] Infrastructure adapters: SqlRepositoryFileRepository, SqlRepositorySymbolRepository, SqlRepositoryDependencyRepository, SqlRepositoryChunkRepository (pgvector cosine semantic search).
- [x] Tree-sitter parser: Python, TypeScript/TSX, JavaScript, Rust, Go (Phase 1); symbol extraction with class→method nesting, per-language dependency extraction; failures non-fatal.
- [x] Language detection (`language_map.py`) with vendor/binary filtering.
- [x] Safe git client (`git.py`): `ls-tree`/`show`/`diff` via argument arrays, validated repo-relative paths, timeouts.
- [x] Embedding providers: NullEmbedder (default) + SentenceTransformerEmbedder (all-MiniLM-L6-v2, 384 dims, optional extra); system works with embeddings disabled.
- [x] Chunking service (symbol-aware, configurable size/overlap).
- [x] Dependency resolver mapping imports to repo files (python/ts/js/rust/go).
- [x] RepositoryIndexService orchestrator: full + incremental/capability indexing, content-hash change detection, reindex, index status; audit `repository.indexed`/`repository.reindexed`.
- [x] FileDiscoveryService + background IndexWorker (polls `SyncJobType.INDEX`, `FOR UPDATE SKIP LOCKED`); auto-enqueue indexing after clone.
- [x] Search service: file/symbol/dependency/structural search + semantic search with graceful unavailable result when embeddings disabled.
- [x] API: POST `/{id}/index`, GET `/{id}/index/status`, POST `/{id}/search`, GET `/{id}/symbols`, GET `/{id}/files`, GET `/{id}/files/{path}/symbols`, GET `/{id}/files/{path}/dependencies` — all behind `validated_claims` + RBAC + response envelope.
- [x] Unit tests: parser, chunking, embedding, discovery, resolver, index service, search service. Integration tests: end-to-end clone→index→parse→store→search, authorization.
- [x] Full validation green: `ruff check .`, 207 tests passing, Alembic 0004→0005 upgrade/downgrade verified, app startup, all 7 intelligence endpoints registered.

## Completed — Feature Pack 6 (Context & Memory Engine, 2026-08-11)

- [x] Migration `0006_context_memory`: `memories` table (UUID PK, workspace FK CASCADE, optional repository/user/created_by FKs, memory_type/scope/status, TEXT content, summary, source_file_path/source_symbol_name/source_commit_hash, confidence, JSONB tags + GIN index, `embedding VECTOR(384)`, timestamps, soft-delete) — reversible upgrade/downgrade.
- [x] Domain (`domain/memory.py`): MemoryType/MemoryScope/MemoryStatus enums, MemoryRecord, ConversationContextEntry, ContextEntry/ContextWindow/ContextSource, ContextRankingConfig; `MemoryRepository` and `ConversationContextStore` ports in `domain/repositories.py`.
- [x] SqlMemoryRepository adapter: workspace isolation + user ownership enforced at the SQL layer; get/list-by-workspace/repository/user, create, update, soft delete, semantic (pgvector cosine), tag (JSONB `@>`), stale marking, delete-by-repository, accessed_at touches.
- [x] RedisConversationContextStore + NullConversationContextStore fallback: `forge:ctx:{session}:{conversation}`, max 100 entries, TTL, session-scoped; graceful omission when Redis unavailable.
- [x] MemoryService: create/get/list/update/delete/archive/restore/reconfirm/search; embedding-on-write optional; audit events; application-layer RBAC (workspace/repository = OWNER/ADMIN/MAINTAINER; user = owner-only).
- [x] ContextAssemblyService: structural (memory + symbols + files + dependencies + conversation) and semantic (memory + chunk vectors) retrieval; normalize → deduplicate → rank (configurable weights) → filter → truncate (8192-token default).
- [x] MemoryMaintenanceService + MemoryMaintenanceWorker (periodic): expire memories, backfill embeddings, hard-delete soft-deleted > 30 days; follows the FP5 worker conventions.
- [x] Post-index invalidation hook in RepositoryIndexService: only memories referencing changed file paths are marked stale; memory failures never fail indexing.
- [x] API: 6 memory endpoints under `/v1/workspaces/{wid}/memories`, POST `/v1/context/assemble`, GET/POST/DELETE `/v1/context/conversation/{conversation_id}`; DI wired in `dependencies.py`; routers in `app.py`.
- [x] Settings: memory/context tuning values with range validation; new audit event types `memory.*` + `context.assembled`.
- [x] Unit tests (memory service, context assembly, conversation context, maintenance, invalidation) + integration tests (full E2E, user-memory isolation, reindex invalidation, Redis conversation).
- [x] Live-infrastructure validation (2026-08-11): Docker PostgreSQL 16 + pgvector 0.8.6 + Redis 7.4 healthy; Alembic upgrade→downgrade→re-upgrade verified; **258 tests passing** with zero skips; `ruff check .` clean; app startup + routes; memory/context/Redis/pgvector/invalidation verified E2E.
- [x] Genuine defects found and fixed during live validation: SQL adapter string→enum conversion; JSONB tag `@>` operator (was LIKE); `update()` lazy-reload after flush (`MissingGreenlet`).
