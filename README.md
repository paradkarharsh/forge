# Forge

Forge is an AI-native software engineering workspace. This repository contains its production foundation: a Tauri desktop shell, Next.js web client, FastAPI service, shared TypeScript packages, and local infrastructure.

## Prerequisites

- Node.js 20.9 or later
- pnpm 9
- Python 3.12
- Docker Desktop
- Rust toolchain and platform prerequisites for Tauri development

## Setup

1. Copy `.env.example` to `.env` and replace `POSTGRES_PASSWORD`.
2. Copy `apps/web/.env.example` to `apps/web/.env.local`.
3. Copy `services/api/.env.example` to `services/api/.env` and replace its database password.
4. Run `pnpm install`.
5. Run `docker compose up -d postgres redis`.
6. In `services/api`, create a virtual environment and run `pip install -e '.[dev]'`.

## Commands

- `pnpm dev` — start workspace development processes.
- `pnpm build` — compile TypeScript applications and packages.
- `pnpm lint` — run TypeScript linting.
- `pnpm typecheck` — run TypeScript checking.
- `docker compose up --build` — start local infrastructure and API.

## Architecture

`apps/` contains clients. `packages/` contains shared types, design tokens, UI, and configuration. `services/api` follows Clean Architecture: domain models are isolated from application use cases, infrastructure adapters, and HTTP presentation.
