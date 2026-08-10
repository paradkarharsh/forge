# Forge Agent Guide

## Product vision

Forge is an AI-native software engineering workspace. It brings repository-aware AI assistance, engineering work, search, project memory, and deployment into one desktop-first workspace, with a complementary web experience.

## Architecture

- Clients: Tauri desktop application and Next.js web application.
- Backend: FastAPI services backed by worker processes.
- Data flow: user → API → services → PostgreSQL/Redis → AI workers.
- Key systems: repository indexer, memory engine, search, and deployment.
- Repository organization: monorepo with `apps/`, `packages/`, and `services/`.

## Tech stack

- Desktop: Tauri
- Web: Next.js
- Backend: FastAPI / Python
- Data: PostgreSQL and Redis
- Delivery: Docker and GitHub Actions
- Testing: Vitest, Pytest, Playwright, and AI evaluation

## Intended folder structure

```text
apps/       # Tauri desktop and Next.js web clients
packages/   # shared UI, types, and utilities
services/   # FastAPI services and workers
.memory/    # durable project memory records
```

## AI agents

Forge defines Planner, Coder, Reviewer, Tester, Architect, Documentation, Memory, and Deployment agents. Their common flow is:

`Input → Context Retrieval → LLM → Validation → Output → User Review`

Agents must use project memory, cite affected files, and require approval before applying changes.

## Coding standards

- Use strict TypeScript and typed Python.
- Enforce linting and formatting.
- Use `feature/*` branches, semantic commits, and PR review.
- Build accessible, keyboard-first, theme-aware, responsive interfaces.
- Keep prompts concise, deterministic, repository-aware, and structured.

## Current implementation status

Milestone 0 project foundation is implemented. It provides the Turborepo workspace, Tauri and Next.js shells, a Clean Architecture FastAPI service, Dockerized PostgreSQL/pgvector and Redis, shared packages, quality tooling, CI, and setup documentation.

Milestone 1 authentication foundation is implemented and validated in `services/api`:

- Clean Architecture layering: `domain/` (errors, records, repository ports, security protocols), `application/` (auth, session, OAuth, workspace services), `infrastructure/` (SQLAlchemy adapters, security, audit, OAuth, cache), `presentation/http/` (routers, DI providers, response contracts).
- Every endpoint responds with the global envelope from `presentation/http/contracts.py`; centralized exception handlers in `presentation/http/errors.py` map domain/validation/database errors to the same error contract.
- Session lifecycle: refresh-token rotation with reuse detection, server-side revocation (logout current/all), expiration cleanup on a background task, throttled `last_active` updates.
- `validated_claims` dependency enforces session revocation at the request level — revoked tokens are rejected immediately, not just on refresh.
- Audit events record user, session, ip, user agent, reason, and a structured JSON payload.
- Dependency injection is wired through FastAPI `Depends` chains in `presentation/http/dependencies.py`; no SQLAlchemy imports exist in the presentation layer outside that module.
- Request-scoped database sessions commit on the happy path and roll back on exceptions via `get_session`.
- Alembic runtime and migrations under `services/api/alembic/`; run with `FORGE_DATABASE_URL=... python -m alembic upgrade head`.
- Full test suite: 121 tests verified passing against live PostgreSQL and Redis (2026-08-04).

Milestone 2 workspace tenancy is implemented in `services/api`:

- `alembic/versions/0003_workspace_tenancy.py` adds a unique, indexed `slug` and `description` to `workspaces` with backfill for existing rows.
- Workspace CRUD in `application/workspaces/workspace_service.py` and `presentation/http/workspaces.py`: create (auto-slug via `slugify` or explicit slug), list, get by id, get by slug, partial update (PATCH preserves omitted fields via `model_fields_set`), and owner-only soft delete (`deleted_at`).
- Membership management: list members, add member (OWNER/ADMIN only; cannot assign owner role), remove member (cannot remove owner), change member role (cannot change owner's role). All build on the `SqlWorkspaceRepository` adapter and the `WorkspaceRepository` protocol.
- Slug validation + uniqueness yield stable error codes (`invalid_slug`, `slug_taken`, `already_member`); new audit events `workspace.updated`, `workspace.deleted`, `workspace.member_added`/`removed`/`role_changed`.
- The `validated_claims` dependency (in `presentation/http/dependencies.py`) enforces session revocation and expiry on every protected endpoint; all workspace/session routes use it.
- JSON response shaping lives in the routers; domain records (`workspace.id`, `.name`, `.slug`, `.description`, `.deleted_at`) feed `_workspace_view`/`_member_view` helpers.

Product features (indexer, memory, search, deployment, workspace UX) are not yet implemented.

Feature Pack 4 repository onboarding is implemented in `services/api`:

- `alembic/versions/0004_repository_onboarding.py` adds `repositories`, `repository_branches`, `repository_sync_jobs`, and `repository_events` with UUID PKs, `workspace_id` foreign keys, indexes, and JSON payload columns.
- Repository domain lives in `domain/repository.py` (records + provider/visibility/clone/sync/job enums); ports were added to `domain/repositories.py` (`RepositoryRepository`, `RepositoryBranchRepository`, `RepositorySyncJobRepository`, `RepositoryEventRepository`). SQLAlchemy adapters live in `infrastructure/repository_*_repository.py`.
- Application services in `application/repositories/`: `repository_service.py` (CRUD/archive/restore/delete with workspace RBAC), `import_service.py` (GitHub URL + local folder; GitLab/Bitbucket can be added as new provider branches without interface changes), `clone_service.py` (remote validation, git clone, default-branch detection, branch discovery, metadata extraction, clone-status transitions), `background_jobs.py` (clone/sync/index queues; indexing not yet performed).
- Repository operations emit both audit events (`audit_events` via `AuditEventType.REPOSITORY_*`) and domain events (`repository_events`).
- `/v1/repositories` router exposes list/create/get/update/delete/import/clone/archive/restore/branches/status behind `validated_claims`; DI wired in `presentation/http/dependencies.py`.
- Tests: `test_repository_service.py`, `test_repository_import.py`, `test_repository_clone.py`, `test_background_jobs.py`, plus integration coverage in `test_integration.py` (CRUD lifecycle, import, authorization).
- Validation fixes (2026-08-10): audit-event expected-set test updated for repository event types; integration-suite rate-limiter isolation via per-test `_reset_rate_limiter` autouse fixture (production limits unchanged); pre-existing ruff lint errors in migration `0001` corrected (formatting only, no schema change). Full suite: **163 tests passing**, ruff clean, Alembic chain verified base→head, app startup confirmed.

Feature Pack 5 repository intelligence is implemented in `services/api`:

- `domain/indexing.py` owns the index records/enums (files, symbols, dependencies, chunks, `IndexStatus`, `SymbolKind`/`DependencyKind`), plus the `TreeSitterParser`, `EmbeddingProvider`, and `GitClient` ports and path/revision validation.
- Migration `0005_repository_intelligence` adds four index tables (chunks store `vector(384)`) and index metadata on `repositories` (`index_status`, `indexed_at`, `file_count`, `symbol_count`).
- `infrastructure/`: safe `git.py` client (`ls-tree`/`show`/`diff`, argument arrays, validated repo-relative paths, timeouts), `treesitter.py` parser (Phase 1 languages: Python, TypeScript/TSX, JavaScript, Rust, Go), `language_map.py` detection, `embedding.py` (`NullEmbedder` default; `SentenceTransformerEmbedder` 384-dims optional), and four SQLAlchemy adapters (files/symbols/dependencies/chunks, pgvector cosine search).
- `application/indexing/`: `file_discovery_service.py`, `chunking_service.py` (symbol-aware), `dependency_resolver.py`, `index_service.py` (orchestrator with content-hash incremental + reindex), `index_worker.py` (consumes `SyncJobType.INDEX`, `FOR UPDATE SKIP LOCKED`), `search_service.py` (structural search always available; semantic search gracefully reports unavailable when embeddings disabled).
- Clone auto-enqueues an index job; `/v1/repositories` gained 7 intelligence endpoints (index, index/status, search, symbols, files, files/{path}/symbols, files/{path}/dependencies) behind `validated_claims` + RBAC.
- Validation (2026-08-11): `ruff check .` clean, **207 tests passing**, Alembic `0004→0005` upgrade/downgrade verified, app startup with the index worker, end-to-end integration test (local-git clone → index → parse → store → search).
