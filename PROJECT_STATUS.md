# Forge Project Status

## Completed features

- Documentation baseline supplied and synthesized.
- High-level product, architecture, AI-agent, component, testing, DevOps, and workspace decisions recorded in project memory.
- Milestone 0 foundation: pnpm/Turborepo workspace, web and desktop shells, FastAPI Clean Architecture service, Docker Compose infrastructure, shared packages, quality tooling, CI, environment templates, and setup documentation.
- **Milestone 1 — Authentication & Workspace Foundation (in progress):**
  - Epic 1: Global response system — success/error envelopes, centralized exception handlers, consistent contracts across every endpoint.
  - Epic 2: OAuth backend — GitHub and Google provider flow with state, PKCE, nonce generation, and audit integration.
  - Epic 3: Session lifecycle — refresh-token rotation with reuse detection, server-side session revocation, expiration cleanup, `last_active` throttling, logout current/all.
  - Epic 4: Audit system — structured audit events carrying session id, ip, user agent, reason, and payload.
  - Epic 5: Repository architecture — repository port interfaces, SQLAlchemy adapters, application services, DTO mapping, FastAPI dependency injection; SQLAlchemy removed from the presentation layer.
  - Epic 6: Alembic runtime (env/ini/mako) and follow-up migration `0002` adding `audit_events`, `oauth_identities`, session context fields, and indexes; upgrade/downgrade verified.
  - Epic 7: Test suite — 80 unit tests (session lifecycle, refresh rotation, reuse detection, authorization, response contracts, exception handlers, audit, security) plus 4 integration tests gated on live PostgreSQL/Redis.

## Remaining features

- Runtime validation against live PostgreSQL and Redis (integration tests) — blocked locally until Docker Desktop/WSL2 or a native Postgres/Redis install is available.
- Product implementation remains: Tauri desktop client behavior, Next.js application surfaces, FastAPI business services and workers, data model, product APIs, repository indexer, memory engine, search, deployment, and observability.
- Detailed product requirements, API contracts, database schema, design tokens, and measurable performance targets need completion before the corresponding build work.

## Current milestone

Milestone 1 — Authentication & Workspace Foundation (in progress).

## Current sprint

Sprint 1 — secure authentication, session rotation, workspace tenancy, and audit.

## Next recommended task

Bring up PostgreSQL + Redis (Docker Compose) and run the integration suite; then begin workspace tenancy product features on top of the completed authentication/session/audit foundation.
