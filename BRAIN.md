# Forge Architectural Memory

## Important decisions

- Forge is an AI-native software engineering workspace, not a standalone code-generation tool.
- The product is desktop-first, implemented with Tauri, and is paired with a Next.js web experience.
- FastAPI services and workers provide the backend execution model.
- PostgreSQL is the durable system of record; Redis provides caching and supporting fast-access state.
- Repository indexing, memory, search, and deployment are first-class systems.
- The v2.0 documentation suite is authoritative over v1.0 material. The v1.0 Master Product Vision is a draft whose detailed content was not inserted.

## Design philosophy

- Keep engineering work in context: navigation, workbench, AI intelligence, and activity are cohesive workspace capabilities.
- Treat AI as a validated, repository-aware collaborator with human review at the end of its flow.
- Prefer reusable foundations over one-off UI or prompt behavior.

## Backend conventions

- Organize backend work into FastAPI services and workers within the monorepo.
- Keep domain/schema, lifecycle, caching, security, and production database concerns explicit.
- Use PostgreSQL for persistence and Redis where low-latency cached state is appropriate.
- Design for logs, metrics, alerts, and backups from the outset.

## API conventions

- Expose REST endpoints and WebSockets.
- Include authentication, pagination, consistent errors, SDK strategy, and lifecycle management.
- Specific route names, schemas, authentication mechanism, and error envelope are not yet specified; define them before implementation rather than guessing.

## UX principles

- Desktop-first, contextual workspace panels.
- Primary workbench layout: Navigator | Workbench | Intelligence Panel | Activity Dock.
- The component system must be accessible, keyboard-first, responsive, and theme-aware.
- Major planned surfaces include landing, login, workspace picker, workbench, search, settings, and deployments.

## Lessons learned

- Documentation includes several high-level placeholder documents. Do not turn their headings into unsupported implementation details.
- The v1.0 suite is an index/reference package; v2.0 documents hold the concrete available decisions.

## Do not forget

- AI changes require user approval before application.
- AI outputs must be validated and identify affected files.
- Prompt design must remain concise, deterministic, repository-aware, and use structured outputs.
- Critical flows require testing before release, including AI evaluation.
