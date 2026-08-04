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
