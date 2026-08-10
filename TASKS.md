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
