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

Milestone 0 project foundation is implemented. It provides the Turborepo workspace, Tauri and Next.js shells, a Clean Architecture FastAPI service, Dockerized PostgreSQL/pgvector and Redis, shared packages, quality tooling, CI, and setup documentation. No product features are implemented.
