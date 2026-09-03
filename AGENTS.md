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

Product features (deployment, workspace UX, LLM/agent integration) are not yet implemented; repository indexing, search, and the context & memory engine are.

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

Feature Pack 6 context & memory engine is implemented in `services/api`:

- `domain/memory.py` owns the memory taxonomy (`MemoryType`: decision/convention/fact/preference/summary/annotation; `MemoryScope`: workspace/repository/user; `MemoryStatus`: active/stale/archived), `MemoryRecord`, `ConversationContextEntry`, the `ContextEntry`/`ContextWindow`/`ContextSource` context model, and the `MemoryRepository` + `ConversationContextStore` ports.
- Migration `0006_context_memory` adds the `memories` table (workspace FK CASCADE, optional repository/user/created_by FKs, TEXT content, JSONB tags with GIN index, `embedding VECTOR(384)`, source linkage, timestamps, soft-delete); reversible.
- `infrastructure/`: `memory_repository.py` (`SqlMemoryRepository` — workspace isolation and user ownership enforced at the SQL layer, pgvector cosine semantic search, JSONB `@>` tag search), `conversation_context.py` (`RedisConversationContextStore` keyed `forge:ctx:{session}:{conversation}`, max 100 entries, TTL; `NullConversationContextStore` fallback so assembly omits conversation gracefully when Redis is down).
- `application/memory/`: `memory_service.py` (CRUD/search/lifecycle, embedding-on-write optional, audit, application-layer RBAC — workspace/repository memory needs OWNER/ADMIN/MAINTAINER, user memory is owner-only), `context_assembly_service.py` (structural + semantic fan-out → normalize → deduplicate → rank with configurable weights → filter → truncate to 8192 tokens), `maintenance_service.py` + `memory_worker.py` (expire memories, backfill embeddings, hard-delete soft-deleted > 30 days).
- Post-index invalidation: `RepositoryIndexService._complete` marks stale only memories whose `source_file_path` is in the changed-path set; a memory failure never fails indexing.
- API: 6 memory endpoints under `/v1/workspaces/{wid}/memories`, POST `/v1/context/assemble`, GET/POST/DELETE `/v1/context/conversation/{conversation_id}`; new audit events `memory.created/updated/deleted/archived/stale_marked/searched` and `context.assembled`.
- Live-infrastructure validation (2026-08-11): Docker PostgreSQL 16 + pgvector 0.8.6 + Redis 7.4; Alembic 0006 upgrade/downgrade/re-upgrade verified; **258 tests passing** with zero skips; `ruff check .` clean; memory CRUD/authorization/user-isolation/context-assembly/repository-intelligence/Redis-conversation/reindex-invalidation verified end-to-end. Three genuine defects fixed during validation: SQL adapter string→enum conversion, JSONB tag `@>` operator, and `update()` lazy-reload after flush.

Feature Pack 7 LLM gateway is implemented in `services/api`:

- Provider-agnostic domain interfaces (`LLMClient`, `ModelRegistry`, `UsageTracker`, `ConversationService`).
- Migration `0007_llm_gateway` adds `conversations`, `messages`, and `usage_events` tables.
- Robust provider resilience, token estimation, cost tracking, streaming responses, and prompt versioning.

Feature Pack 8 Agentic Development Engine is implemented in `services/api`:

- **FP8-A (Domain & Persistence Schema):** Domain models (`AgentSessionRecord`, `AgentStepRecord`, `AgentToolCallRecord`, `AgentApprovalRecord`), lifecycle state machine, immutable limits/metrics, SHA-256 canonical argument hashing (`compute_arguments_hash`), and Alembic migration `0008_agent_engine` (`agent_sessions`, `agent_steps`, `agent_tool_calls`, `agent_approvals`).
- **FP8-B (Tool System & Policy Engine):** Exactly 12 provider-neutral tools (7 read, 3 write, 1 git, 1 terminal), deterministic `PolicyEngine` with workspace RBAC and risk evaluation (`LOW`, `HIGH`, `CRITICAL`), approval requirement lifecycle, untrusted path containment, and pattern-based secret redaction (`redact_secrets`).
- **FP8-C (Agent Worker Runtime & Orchestration):** Bounded `AgentOrchestrator` execution loop with state suspension upon requiring human approval, context injection (FP6 memory + repository context), LLM Gateway tool calling (FP7), durable job execution via existing sync job infrastructure (`AGENT_EXECUTE`, `AGENT_RESUME`), `RedisAgentCoordinator` fast-path notification and cancellation signaling, and hard execution boundary enforcement.
- **FP8-D (Persistence Adapters, Agent API, Approval API, and SSE Streaming):**
  - Concrete persistence adapters: `SqlAgentSessionRepository`, `SqlAgentStepRepository`, `SqlAgentToolCallRepository`, `SqlAgentApprovalRepository` (row-level `with_for_update` for atomic decision transitions and idempotent retries), and `SqlAgentJobQueue` (`with_for_update(skip_locked=True)`).
  - Application boundary `AgentService` enforcing BOLA/IDOR isolation, workspace RBAC, cryptographic argument hash verification (`hmac.compare_digest`), worker notification, and lifecycle events.
  - HTTP presentation router `agent_router` exposing all 11 endpoints under `/v1/workspaces/{workspace_id}/agents`: create, list, get session, run, cancel, steps, tool-calls, approvals, grant, deny, and events.
  - Real-time SSE event streaming (`/events`): bounded Redis replay buffer (`forge:agent:event_log:{session_id}`, 500 events max, 1h TTL), `Last-Event-ID` resume filtering, deduplication between replay and live Pub/Sub (`forge:agent:events:{session_id}`), secret redaction on all payloads, periodic keepalive heartbeat comment (`: ping\n\n`), and clean termination on terminal status.
- **FP8-E (Audit, Usage, Retention & Production Hardening):**
  - All 21 lifecycle audit events registered in `AuditEventType` and emitted across session creation, run, planning, running, steps, tool calls, approvals, resumption, cancellation, timeout, and limits.
  - Secret and reasoning scrubbing: all audit payloads filtered via `redact_secrets()` and stripped of sensitive keys (`chain_of_thought`, `reasoning`, `secret`, `password`, `token`, `api_key`).
  - Durable usage and cost accounting: `agent_session_id` foreign key on `usage_events`, provider-neutral tracking of LLM counts, retries (`total_llm_retries`), tool calls, token usage, cost, and duration surviving suspension/resumption without double-counting.
  - Strict limit boundary enforcement: wall time (900s), LLM calls (30, 31st rejected), tool calls (50, 51st rejected in both orchestration loop and resume path), output truncation (64KB cap with notice), and observation cap (8KB).
  - Operational maintenance and recovery: `AgentMaintenanceService` providing conservative stale session recovery with Redis distributed lock verification, approval expiration recovery, and 30-day retention cleanup of terminal sessions (active sessions strictly preserved).
  - Migration `0009_agent_hardening`: adds `last_heartbeat_at`, `worker_id`, retention/heartbeat indexes to `agent_sessions`, and `agent_session_id` to `usage_events`.
  - Full suite: **516 tests passing**, 20 skipped (live Docker services), 0 failures; `ruff check .` clean; app startup verified.
- **FP8-F (Prompt 1/2: Agent Workspace, Creation Flow, API Integration & Session UI):**
  - Typed client integration in `apps/web/src/lib/api`: strict TypeScript types matching FP8 models, typed REST client for all 8 agent operations, and resilient SSE client with `: ping` watchdog, deduplication, and exponential backoff reconnects.
  - Reactive hooks: `useAgentSession`, `useAgentEvents`, `useElapsedTime`.
  - Component library: 9-state status badge with animated glow, filterable agent list/table, validated agent creation form with character counting and expandable limit configuration, interactive session header, unified chronological activity timeline with filter tabs, tool invocation cards with risk badges (`LOW`/`HIGH`/`CRITICAL`), and telemetry sidebar (tokens, cost USD, limits).
  - Routes: `/workspaces/[workspaceId]/agents`, `/workspaces/[workspaceId]/agents/new`, `/workspaces/[workspaceId]/agents/[agentId]`, and repository-scoped variants.
  - Quality and verification: 15 Vitest tests passing across 4 test suites, strict `tsc --noEmit` clean, ESLint clean (`--max-warnings=0`), production Next.js build verified with SSG, 535 backend Pytest tests passing (0 failures), ruff clean.

Canonical Visual System & Web Redesign is implemented in `apps/web` and `packages/design-tokens`:

- **Design Philosophy:** "Precision over decoration." Zero vibecoded purple/blue neon gradients, zero decorative AI sparkles, and zero generic marketing templates.
- **Brand Identity:** Minimal rounded-bar "F" vector emblem (vertical pillar, top bar, middle bar) and geometric "FORGE" wordmark with optional tagline "BUILD BETTER. SHIP FASTER." in warm ivory/champagne.
- **Dual-Theme Design System:** Complete semantic tokens in `packages/design-tokens/src/tokens.css` with dark theme (near-black charcoal `#080A0A`, surfaces `#0D1010` to `#151918`, subtle borders `#1F2423`, warm white text `#EDEDEC`) and light theme (warm ivory/cream `#FAF8F5`, surfaces `#FFFFFF`/`#F3EFEA`, borders `#E5E0D8`, charcoal text `#121515`).
- **Restrained Status Taxonomy:** Muted olive green (`#78B18A`) for running/completed/success, muted amber (`#E5A952`) for approval/warning, restrained red (`#D66A6A`) for failed/error, and warm ivory (`#F4EFE6`) for accents.
- **Transformed Landing Page (`/`):** High-aesthetic, responsive developer landing page matching Reference 1 with sticky blurred navbar, large confident hero, interactive realistic Agent Workspace preview (toggleable activity feed, changed files, and syntax-aware diffs), social proof metrics, asymmetric architectural capability showcases, 5-step engineering lifecycle, final CTA, and clean footer.
- **Authenticated Developer Workspace Shell (`AppShell`):** Collapsible sidebar with Forge logo, workspace selector, navigation links (Dashboard, Agents, Repositories, Memory, Settings), active agents badge, user profile, and theme toggle; top command bar with breadcrumbs, command palette shortcut (`⌘K`), backend gateway connectivity indicator, and quick `+ New Agent` action.
- **Workspace Dashboard (`/workspaces/[id]`):** Prioritizes developer-critical telemetry (active agents, pending approvals, completed tasks, AST repository index status, pending approval banners, recent activity).
- **Security & Quality:** Strict zero `dangerouslySetInnerHTML`, pure React text nodes for diffs/tool outputs, WCAG 2.1 AA accessibility, 29 Vitest tests passing across 9 test suites (including visual system validation), strict `tsc --noEmit` clean, ESLint clean (`--max-warnings=0`), production Next.js build verified with SSG (12 static pages), 535 backend Pytest tests passing (0 failures), and Ruff clean. Permanent design documentation in `docs/design/FORGE-DESIGN-SYSTEM.md`.


