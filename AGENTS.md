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

Milestone 1 authentication foundation is implemented in `services/api`:

- Clean Architecture layering: `domain/` (errors, records, repository ports, security protocols), `application/` (auth, session, OAuth, workspace services), `infrastructure/` (SQLAlchemy adapters, security, audit, OAuth, cache), `presentation/http/` (routers, DI providers, response contracts).
- Every endpoint responds with the global envelope from `presentation/http/contracts.py`; centralized exception handlers in `presentation/http/errors.py` map domain/validation/database errors to the same error contract.
- Session lifecycle: refresh-token rotation with reuse detection, server-side revocation (logout current/all), expiration cleanup on a background task, throttled `last_active` updates.
- Audit events record user, session, ip, user agent, reason, and a structured JSON payload.
- Dependency injection is wired through FastAPI `Depends` chains in `presentation/http/dependencies.py`; no SQLAlchemy imports exist in the presentation layer outside that module.
- Alembic runtime and migrations under `services/api/alembic/`; run with `FORGE_DATABASE_URL=... python -m alembic upgrade head`.

Product features (indexer, memory, search, deployment, workspace UX) are not yet implemented.
