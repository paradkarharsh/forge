# Forge Project Status

## Completed features

- Documentation baseline supplied and synthesized.
- High-level product, architecture, AI-agent, component, testing, DevOps, and workspace decisions recorded in project memory.
- Milestone 0 foundation: pnpm/Turborepo workspace, web and desktop shells, FastAPI Clean Architecture service, Docker Compose infrastructure, shared packages, quality tooling, CI, environment templates, and setup documentation.
- **Milestone 1 — Authentication & Workspace Foundation (complete):**
  - Epic 1: Global response system — success/error envelopes, centralized exception handlers, consistent contracts across every endpoint.
  - Epic 2: OAuth backend — GitHub and Google provider flow with state, PKCE, nonce generation, and audit integration.
  - Epic 3: Session lifecycle — refresh-token rotation with reuse detection, server-side session revocation, expiration cleanup, `last_active` throttling, logout current/all.
  - Epic 4: Audit system — structured audit events carrying session id, ip, user agent, reason, and payload.
  - Epic 5: Repository architecture — repository port interfaces, SQLAlchemy adapters, application services, DTO mapping, FastAPI dependency injection; SQLAlchemy removed from the presentation layer.
  - Epic 6: Alembic runtime (env/ini/mako) and follow-up migration `0002` adding `audit_events`, `oauth_identities`, session context fields, and indexes; upgrade/downgrade verified.
  - Epic 7: Test suite — 80 unit tests plus 4 integration tests, all passing against live PostgreSQL/Redis.
- **Milestone 2 — Workspace Tenancy (complete):**
  - Feature Pack 3: Workspace tenancy product behavior on top of the session/audit foundation.
  - Migration `0003` adds a unique, indexed `slug` and a `description` column to `workspaces` (backfilled for existing rows).
  - Workspace CRUD: create (auto-slug from name or explicit slug), list, get by id, get by slug, partial update (PATCH with `model_fields_set` so omitted fields are preserved), and owner-only soft delete.
  - Membership management: list members, add member (OWNER/ADMIN only, cannot assign owner role), remove member (cannot remove owner), change role (cannot change owner's role). All operations emit structured audit events.
  - Slug validation + uniqueness enforcement with machine-readable error codes (`invalid_slug`, `slug_taken`, `already_member`).
  - New audit event types: `workspace.deleted`, `workspace.updated`, `workspace.member_added`, `workspace.member_removed`, `workspace.member_role_changed`.
  - `validated_claims` dependency now also rejects expired sessions (not just revoked ones).
- **Infrastructure validation (complete, 2026-08-04):** Docker Compose services (PostgreSQL 16 + pgvector 0.8.6, Redis 7.4) verified healthy; Alembic migrations run clean; full suite of **121 tests passing** against live infrastructure.
  - Bug fixes applied during validation: request-scoped session dependency now commits; `validated_claims` enforces session revocation server-side; corrected duplicate-register error code assertion.
- **Feature Pack 4 — Repository Onboarding (complete, 2026-08-04):**
  - Migration `0004_repository_onboarding` adds `repositories`, `repository_branches`, `repository_sync_jobs`, and `repository_events` with UUID PKs, workspace FKs, and indexes.
  - Repository domain (`domain/repository.py`): records + enums (provider, visibility, clone status, sync status, job type/status); ports added to `domain/repositories.py`.
  - Repository CRUD service with workspace RBAC: create, list, get, partial update, archive, soft delete, restore.
  - Import service (GitHub URL + local folder) with a provider-strategy shape so GitLab/Bitbucket slot in without interface changes.
  - Clone service: remote verification, `git clone`, default-branch detection, branch discovery, metadata extraction (size, last commit hash), status transitions pending → cloning → ready/failed.
  - Background job service provides clone/sync/index queues; the index queue exists but does not yet index.
  - Audit events for created/imported/cloned/updated/archived/restored/deleted plus a domain `repository_events` log.
  - API `/v1/repositories` router exposing all endpoints behind `validated_claims` and the global response contract; DI wired in `dependencies.py`.
  - New unit tests (CRUD, import, clone, status, background jobs) and integration tests (CRUD lifecycle, import, authorization) — full suite green and ruff clean.
- **Feature Pack 4 validation fixes (complete, 2026-08-10):**
  - Updated `test_audit.py` expected-event-set assertion to include all 7 `repository.*` audit event types added by FP4.
  - Added per-test `_reset_rate_limiter` autouse fixture to `test_integration.py` that clears the in-memory `RateLimitMiddleware.hits` dict between tests, preventing rate-limit budget exhaustion across the session-scoped integration client. Production rate limits are unchanged.
  - Fixed 7 pre-existing ruff lint errors (E702 semicolons, E501 line length) in `alembic/versions/0001_auth_workspace.py` — formatting only, no schema or behavior change.
  - Full validation: `ruff check .` clean, **163 tests passing** (150 unit + 13 integration), Alembic chain base↔head verified (upgrade, downgrade, re-upgrade), app startup confirmed with all 8 repository endpoints registered.
- **Feature Pack 5 — Repository Intelligence (complete, 2026-08-11):**
  - Migration `0005_repository_intelligence` adds `repository_files`, `repository_symbols`, `repository_dependencies`, `repository_chunks` (pgvector `vector(384)`) and repository index metadata columns (`index_status`, `indexed_at`, `file_count`, `symbol_count`); reversible.
  - Indexing pipeline built on domain ports: safe git client (`ls-tree`/`show`/`diff`, validated paths, argument arrays, timeouts), tree-sitter parser (Python, TypeScript/TSX, JavaScript, Rust, Go), symbol-aware chunking, dependency resolution, and optional embeddings.
  - Embedding providers: `NullEmbedder` (default — system fully works with embeddings disabled) and local `SentenceTransformerEmbedder` (`all-MiniLM-L6-v2`, 384 dims, optional `embeddings` extra). No second embedding dimension; exact cosine similarity until real volume is measured.
  - Background `IndexWorker` consumes the FP4 `SyncJobType.INDEX` queue (`FOR UPDATE SKIP LOCKED`); a successful clone now auto-enqueues indexing.
  - Incremental capability via content-hash change detection + `git diff --name-status`; separate from the not-yet-built sync trigger.
  - Search service: structural (files, symbols, dependencies) always available; semantic search reports `available: false` gracefully when embeddings disabled.
  - New endpoints: POST `/{id}/index`, GET `/{id}/index/status`, POST `/{id}/search`, GET `/{id}/symbols`, GET `/{id}/files`, GET `/{id}/files/{path}/symbols`, GET `/{id}/files/{path}/dependencies` — behind `validated_claims` + workspace RBAC + global response envelope.
  - New tests: parser, chunking, embedding, discovery, dependency resolver, index service, search service unit tests, plus end-to-end integration (real local git repo clone → index → parse → store → search) and authorization tests.
  - Full validation green: `ruff check .`, **207 tests passing**, Alembic `0005` upgrade/downgrade verified, app startup with index worker, all 7 intelligence endpoints registered.
- **Feature Pack 6 — Context & Memory Engine (complete, validated 2026-08-11):**
  - Migration `0006_context_memory` adds the `memories` table: UUID PK, workspace FK (CASCADE), optional repository/user/created_by FKs, memory_type/scope/status, TEXT content, summary, source linkage (file path/symbol/commit), confidence, JSONB tags (GIN index), `embedding VECTOR(384)`, timestamps, soft-delete; reversible.
  - Domain (`domain/memory.py`): `MemoryType` (decision/convention/fact/preference/summary/annotation), `MemoryScope` (workspace/repository/user), `MemoryStatus` (active/stale/archived), `MemoryRecord`, `ConversationContextEntry`, `ContextEntry`/`ContextWindow`/`ContextSource`, `ContextRankingConfig`; `MemoryRepository` and `ConversationContextStore` ports.
  - MemoryService: CRUD, search (semantic + tags), archive/restore/reconfirm, embedding-on-write (optional), audit, and application-layer RBAC — workspace/repository memory requires OWNER/ADMIN/MAINTAINER; user memory visible only to its owner (enforced at the SQL adapter level too).
  - ContextAssemblyService: fan-out retrieval combining memory + repository intelligence (symbols/files/dependencies) + ephemeral conversation context + semantic (memory & chunk vectors when embeddings enabled); normalize → deduplicate → rank (configurable weights) → filter → truncate (default 8192 tokens).
  - Memory maintenance worker (periodic): expire memories (`expires_at` → stale), backfill missing embeddings, hard-delete soft-deleted records older than 30 days.
  - Post-index invalidation: after a successful index, only memories whose `source_file_path` is in the changed-path set are marked stale; a memory failure never fails indexing.
  - Ephemeral conversation context in Redis (`forge:ctx:{session}:{conversation}`, max 100 entries, TTL min(session, 24h)); never auto-promoted to durable memory; graceful omission when Redis is down.
  - API: 6 memory endpoints under `/v1/workspaces/{wid}/memories`, POST `/v1/context/assemble`, GET/POST/DELETE `/v1/context/conversation/{conversation_id}` — behind `validated_claims` + RBAC + global envelope.
  - New audit events: `memory.created/updated/deleted/archived/stale_marked/searched`, `context.assembled`.
  - **Live-infrastructure validation (2026-08-11):** Docker PostgreSQL 16 + pgvector 0.8.6 and Redis 7.4 healthy; Alembic chain base→0006 upgrade, 0006 downgrade, re-upgrade verified; **258 tests passing** (no skips) against live PostgreSQL + Redis; `ruff check .` clean; app startup + all routes registered; memory CRUD/authorization/user-isolation/context-assembly/repository-intelligence/Redis-conversation/reindex-invalidation verified end-to-end.
  - Three genuine defects found and fixed during live validation: SQL adapter returned plain strings instead of enums; JSONB `tags` used a `LIKE` expression instead of `@>`; `update()` triggered a lazy reload after flush (`MissingGreenlet`).

## Remaining features

- Product implementation remains: Tauri desktop client behavior, Next.js application surfaces, LLM/agent integration (the context & memory layer is ready to feed it), repository sync trigger, deployment, and observability.
- Detailed product requirements, API contracts, database schema, design tokens, and measurable performance targets need completion before the corresponding build work.

## Current milestone

Milestone 5 — Context & Memory Engine (complete). Next: workspace invites & membership UX, then LLM/agent integration on top of the context window, and repository sync + client surfaces for indexing/search.

## Current sprint

Sprint 5 — repository sync / next product milestone.

## Next recommended task

Wire the FP5 incremental-index capability to a repository sync trigger (periodic/event-driven), then connect the FP6 context window to the future LLM/agent layer and surface search through the Next.js/Tauri clients.
