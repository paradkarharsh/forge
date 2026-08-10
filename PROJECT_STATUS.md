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

## Remaining features

- Product implementation remains: Tauri desktop client behavior, Next.js application surfaces, FastAPI workers, repository indexer, memory engine, search, deployment, and observability.
- Detailed product requirements, API contracts, database schema, design tokens, and measurable performance targets need completion before the corresponding build work.

## Current milestone

Milestone 3 — Repository Onboarding (complete). Next: workspace invites & membership UX, then the repository indexer vertical slice.

## Current sprint

Sprint 4 — repository indexing / next product milestone.

## Next recommended task

Select and document the repository-indexing vertical slice (indexer worker, memory engine, search), then build it end-to-end through the Next.js/Tauri surfaces.
