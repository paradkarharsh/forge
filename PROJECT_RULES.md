# Forge Project Rules

These rules are the project baseline and may only be changed by an explicit, documented architecture decision.

## Design language

- Use the Forge Frame design language defined by the design-system documentation.
- Maintain a desktop-first workspace with contextual panels.
- Provide a consistent, accessible, keyboard-first, responsive, theme-aware component experience.
- Build reusable components for foundational controls and workspace surfaces; core examples include buttons, inputs, cards, tables, command palette, workbench, terminal, and AI panel.

## Coding rules

- Write strict TypeScript and typed Python.
- Apply linting and formatting consistently.
- Use semantic commits, `feature/*` branches, and PR review.
- Do not add application behavior that is unsupported by the project documentation without first recording an approved decision.

## Architecture rules

- Preserve the monorepo boundary: `apps/`, `packages/`, and `services/`.
- Keep desktop (Tauri), web (Next.js), backend (FastAPI), workers, PostgreSQL, and Redis responsibilities separate.
- Treat repository indexing, memory, search, and deployment as architecture-level systems.
- API work must account for REST, WebSockets, authentication, pagination, errors, SDK strategy, and lifecycle.

## Performance and reliability targets

- No numeric performance budgets are approved yet; do not invent them.
- Critical user flows must be tested before release.
- CI/CD must use GitHub Actions, Docker, and automated tests.
- Production operations must include logs, metrics, alerts, and backups.

## Security requirements

- API authentication is required.
- Backend schema and lifecycle work must explicitly address security.
- AI agents must retrieve project context, validate their outputs, cite affected files, and receive user approval before applying changes.

## UI principles

- Make the workspace navigable by keyboard and usable across supported viewport sizes.
- Respect the Forge Frame typography, color, spacing, motion, and interaction guidance when detailed design tokens become available.
- Keep AI assistance contextual to the repository and current work, while retaining user review and control.
