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

## Next — Milestone 1 remaining / Milestone 2

- [ ] Run integration validation against live PostgreSQL and Redis (requires Docker/WSL2 or native installs).
- [ ] Complete workspace tenancy product behavior on top of the session/audit foundation.
- [ ] Define authentication architecture and threat model.
- [ ] Define Forge Frame design tokens and component specifications in detail.
- [ ] Select and document the first user-facing vertical slice.
