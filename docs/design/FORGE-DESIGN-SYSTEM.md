# Forge Canonical Design System

## 1. Vision & Brand Identity
Forge is an AI-native software engineering workspace built for serious developers. The visual identity communicates precision, control, calm speed, and engineering discipline.

- **Logo**: Minimal rounded-bar "F" emblem (vertical rounded pillar + two horizontal crossbars) paired with the uppercase geometric "FORGE" wordmark.
- **Tagline**: `BUILD BETTER. SHIP FASTER.`
- **Design Stance**: "Precision over decoration." Zero neon gradients, zero decorative sparkles, zero gaming aesthetics, zero generic SaaS card grids.

---

## 2. Color System & Semantic Tokens

Forge is dual-themed with first-class Dark and Light mode support governed by semantic CSS tokens.

### Dark Theme (Default)
- **Background**: `#080A0A` (near-black charcoal)
- **Primary Surface**: `#0D1010`
- **Secondary Surface**: `#111515`
- **Elevated Surface**: `#151918`
- **Subtle Borders**: `#1F2423`
- **Border Highlight**: `#2C3331`
- **Primary Text**: `#EDEDEC` (warm white)
- **Secondary Text**: `#9EA3A2` (muted warm gray)
- **Muted Text**: `#626867` (low-contrast gray)
- **Primary Accent**: `#F4EFE6` / `#E8DECE` (warm ivory / champagne)
- **Success / Active**: `#78B18A` (muted olive green, surface `#111D15`, border `#203827`)
- **Warning**: `#E5A952` (muted amber, surface `#20160A`, border `#3F2913`)
- **Danger / Error**: `#D66A6A` (restrained red, surface `#221214`, border `#442024`)

### Light Theme
- **Background**: `#FAF8F5` (warm ivory / cream)
- **Primary Surface**: `#FFFFFF`
- **Secondary Surface**: `#F3EFEA`
- **Elevated Surface**: `#FFFFFF` (subtle shadow)
- **Subtle Borders**: `#E5E0D8`
- **Border Highlight**: `#D5CEC4`
- **Primary Text**: `#121515` (charcoal)
- **Secondary Text**: `#5F6664`
- **Muted Text**: `#8E9694`
- **Primary Accent**: `#1C201F` (high-contrast charcoal with ivory foreground `#F4EFE6`)
- **Success**: `#28663C` (surface `#EEF5F0`, border `#C4DECB`)
- **Warning**: `#8F5715` (surface `#FDF6EC`, border `#EAD4B7`)
- **Danger**: `#A62D36` (surface `#FDF0F1`, border `#EBBEC2`)

---

## 3. Typography & Hierarchy
- **Primary Font Stack**: Clean system sans-serif (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`).
- **Monospace Font Stack**: Compact tabular monospace (`ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`).
- **Hero Headings**: Large, tight letter-spacing (`tracking-tight`), line-height `1.08`.
- **Application UI**: High information density, compact labels (`text-xs`, `text-[11px]`, `text-[10px]`).

---

## 4. Border & Radius Geometry
- Small radius is preferred: `var(--forge-radius-sm)` (4px), `var(--forge-radius-md)` (6px), `var(--forge-radius-lg)` (8px).
- Restrained 1px borders using `--forge-border`.
- No excessive glowing drop-shadows; subtle micro-shadows only.

---

## 5. Animation & Motion Philosophy
- **Principles**: FAST, SMOOTH, SUBTLE, PURPOSEFUL.
- **Micro-interactions**: 150ms-200ms ease transitions on interactive hover and tab changes.
- **Status Pulses**: Restrained opacity pulsing on active indicators (olive green dot).
- **Reduced Motion**: All animations disable immediately under `@media (prefers-reduced-motion: reduce)`.

---

## 6. Landing Page Architecture
1. **Navbar**: ForgeLogo, high-level navigation, theme toggle, and primary CTA.
2. **Hero**: Confident statement ("Build better. Ship faster. With AI agents."), concise explanation, dual action buttons.
3. **Product Preview**: Realistic interactive preview of the Forge Agent Workspace (Activity Timeline, Changed Files, Diff Review).
4. **Engineering Proof**: Real operational metrics (100% Repository-Aware, 50 Bounded Tool Calls, 0 Unauthorized Writes, 8,192 Token Context).
5. **Core Capabilities**: Asymmetric layout highlighting Clean Architecture agent execution, Tree-sitter AST, and Human Authorization.
6. **Workflow Showcase**: 5-step engineering progression.
7. **Final CTA & Footer**: Direct launch link, documentation, and source code links.

---

## 7. Authenticated Application Architecture
- **AppShell**:
  - Persistent, compact left sidebar with logo, workspace switcher, nav links (Dashboard, Agents, Repositories, Memory, Settings), user profile, and ThemeToggle.
  - Top command bar with quiet breadcrumb trail, `⌘K` command shortcut, backend gateway connectivity status, and quick `+ New Agent` action.
  - Responsive mobile drawer.
- **Agent Session Workspace**:
  - Session Header: Objective, status badge, live elapsed timer, cancellation control.
  - Main Work Area: Tabbed Activity Feed, Changed Files list, Unified Diff Review.
  - Approval Panel: Prominent, restrained amber container with warm ivory "Approve & Resume" button and red outline "Deny" button.
  - Sidebar: Live token consumption, estimated USD cost, and execution limits.

---

## 8. Security & Accessibility Standards
- **Zero XSS**: Code diffs and tool outputs render exclusively as pure React text elements without `dangerouslySetInnerHTML`.
- **WCAG 2.1 AA**: Contrast ratios preserved across both Dark and Light palettes.
- **Keyboard First**: Complete tab navigation, visible focus rings (`focus-visible:ring-1`), Enter/Space triggers, and Escape key modal dismissals.
