'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  Code2,
  FileCode,
  GitCommit,
  ListTodo,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Wifi,
} from 'lucide-react';
import { ForgeLogo } from '@/components/brand/forge-logo';
import { ThemeToggle } from '@/components/theme/theme-toggle';

export default function HomePage() {
  const demoWorkspaceId = '00000000-0000-0000-0000-000000000001';
  const [previewTab, setPreviewTab] = useState<'activity' | 'files' | 'diff'>('activity');

  return (
    <div className="min-h-screen bg-[var(--forge-bg)] text-[var(--forge-text-primary)] flex flex-col font-sans selection:bg-[var(--forge-accent)] selection:text-[var(--forge-accent-foreground)]">
      {/* Sticky Navbar */}
      <header className="sticky top-0 z-50 border-b border-[var(--forge-border)] bg-[var(--forge-surface)]/85 backdrop-blur-md px-4 sm:px-8 h-14 flex items-center justify-between transition-colors">
        <div className="flex items-center gap-8">
          <Link href="/" className="hover:opacity-90 transition-opacity">
            <ForgeLogo size="sm" showTagline={false} />
          </Link>

          <nav className="hidden md:flex items-center gap-6 text-xs text-[var(--forge-text-secondary)] font-medium">
            <a href="#product" className="hover:text-[var(--forge-text-primary)] transition-colors">
              Product
            </a>
            <a href="#agents" className="hover:text-[var(--forge-text-primary)] transition-colors">
              Agents
            </a>
            <a href="#intelligence" className="hover:text-[var(--forge-text-primary)] transition-colors">
              Intelligence
            </a>
            <a href="#safety" className="hover:text-[var(--forge-text-primary)] transition-colors">
              Safety
            </a>
            <a href="#workflow" className="hover:text-[var(--forge-text-primary)] transition-colors">
              Workflow
            </a>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link
            href={`/workspaces/${demoWorkspaceId}/agents`}
            className="hidden sm:inline-flex items-center text-xs font-medium text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] px-2.5 py-1.5 transition-colors"
          >
            Workspace
          </Link>
          <Link
            href={`/workspaces/${demoWorkspaceId}/agents/new`}
            className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-3 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors"
          >
            <span>Start building free</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-16 sm:pt-24 pb-12 sm:pb-16 px-4 sm:px-8 max-w-6xl mx-auto w-full flex flex-col items-center text-center space-y-6">
        {/* Subtle Announcement Pill */}
        <div className="inline-flex items-center gap-2 rounded-full border border-[var(--forge-border)] bg-[var(--forge-surface)] px-3 py-1 text-xs text-[var(--forge-text-secondary)] shadow-2xs">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--forge-success)] animate-pulse" />
          <span className="font-mono text-[11px] uppercase tracking-wider text-[var(--forge-text-primary)] font-semibold">
            Forge 1.0 Release
          </span>
          <span className="text-[var(--forge-border)]">•</span>
          <span>Durable Agentic Engine</span>
        </div>

        {/* Large Confident Typography */}
        <h1 className="text-4xl sm:text-6xl md:text-7xl font-bold tracking-tight text-[var(--forge-text-primary)] max-w-4xl leading-[1.08]">
          Build better.
          <br />
          Ship faster.
          <br />
          <span className="text-[var(--forge-text-secondary)] font-medium">With AI agents.</span>
        </h1>

        {/* Concise Supporting Copy */}
        <p className="max-w-2xl text-sm sm:text-base text-[var(--forge-text-secondary)] leading-relaxed font-normal">
          Forge is the repository-aware software engineering workspace. Formulate plans, inspect AST symbols, execute terminal tools with human authorization, and build software with durable project memory.
        </p>

        {/* Hero CTAs */}
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href={`/workspaces/${demoWorkspaceId}/agents/new`}
            className="inline-flex items-center gap-2 rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-5 py-2.5 text-xs sm:text-sm font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors"
          >
            <span>Start building for free</span>
            <ArrowRight className="h-4 w-4" />
          </Link>

          <Link
            href={`/workspaces/${demoWorkspaceId}/agents`}
            className="inline-flex items-center gap-2 rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] hover:border-[var(--forge-border-highlight)] hover:bg-[var(--forge-surface-secondary)] px-4 py-2.5 text-xs sm:text-sm font-medium text-[var(--forge-text-primary)] transition-colors"
          >
            <span>Explore Workspace</span>
          </Link>
        </div>

        <p className="text-[11px] font-mono text-[var(--forge-text-muted)] tracking-wide">
          Self-hostable • Clean Architecture • Docker & PostgreSQL • Zero Lock-in
        </p>
      </section>

      {/* Hero Product Visual (Interactive Realistic Agent Workspace Preview) */}
      <section id="product" className="px-4 sm:px-8 max-w-6xl mx-auto w-full pb-20">
        <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] shadow-2xl overflow-hidden">
          {/* Mock Workspace Header */}
          <div className="border-b border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="font-mono text-[11px] text-[var(--forge-text-muted)]">
                  task-8eaf8ea
                </span>
                <span className="text-[var(--forge-border)]">•</span>
                <h3 className="text-xs sm:text-sm font-semibold text-[var(--forge-text-primary)] truncate font-mono">
                  Refactor auth session lifecycle with argon2id and cryptographic audit
                </h3>
                <span className="inline-flex items-center gap-1 text-[10px] font-mono font-medium px-2 py-0.2 rounded bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--forge-success)] animate-pulse" />
                  <span>Running</span>
                </span>
              </div>
              <div className="flex items-center gap-4 text-[11px] font-mono text-[var(--forge-text-muted)]">
                <span>Repository: <strong className="text-[var(--forge-text-secondary)]">forge/main</strong></span>
                <span>Elapsed: <strong className="text-[var(--forge-text-secondary)]">00:42.5s</strong></span>
                <span>Model: <strong className="text-[var(--forge-text-secondary)]">gpt-4o</strong></span>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--forge-success)] font-mono">
                <Wifi className="h-3 w-3" />
                <span className="text-[10px]">Live Pub/Sub</span>
              </span>
            </div>
          </div>

          {/* Workspace Body: Tabs & Live Preview */}
          <div className="p-4 sm:p-5 flex flex-col lg:flex-row gap-5">
            {/* Center Stage */}
            <div className="flex-1 min-w-0 space-y-4">
              {/* Approval Callout in preview */}
              <div className="rounded border border-[var(--forge-warning-border)] bg-[var(--forge-warning-surface)] p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                <div className="flex items-center gap-2.5">
                  <ShieldAlert className="h-4 w-4 text-[var(--forge-warning)] shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-[var(--forge-text-primary)]">
                      Human Approval Required
                    </p>
                    <p className="text-[11px] text-[var(--forge-text-secondary)] font-mono">
                      Tool: file.modify • Target: src/auth/session_service.py
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <span className="rounded border border-[var(--forge-border)] px-2 py-0.5 text-[11px] font-medium text-[var(--forge-text-muted)]">
                    Deny
                  </span>
                  <span className="rounded bg-[var(--forge-accent)] text-[var(--forge-accent-foreground)] px-2.5 py-0.5 text-[11px] font-semibold">
                    Approve & Resume
                  </span>
                </div>
              </div>

              {/* Tab Bar */}
              <div className="flex items-center space-x-1.5 border-b border-[var(--forge-border)] pb-2 text-xs">
                <button
                  type="button"
                  onClick={() => setPreviewTab('activity')}
                  className={`inline-flex items-center space-x-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                    previewTab === 'activity'
                      ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)]'
                      : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                  }`}
                >
                  <ListTodo className="h-3.5 w-3.5" />
                  <span>Activity Timeline</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPreviewTab('files')}
                  className={`inline-flex items-center space-x-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                    previewTab === 'files'
                      ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)]'
                      : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                  }`}
                >
                  <FileCode className="h-3.5 w-3.5" />
                  <span>Changed Files (3)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPreviewTab('diff')}
                  className={`inline-flex items-center space-x-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                    previewTab === 'diff'
                      ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)]'
                      : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                  }`}
                >
                  <GitCommit className="h-3.5 w-3.5" />
                  <span>Diff Review (+442)</span>
                </button>
              </div>

              {/* Tab Display Area */}
              {previewTab === 'activity' && (
                <div className="space-y-2 text-xs font-mono">
                  <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-2.5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[var(--forge-success)] shrink-0" />
                      <span className="text-[var(--forge-text-primary)] font-medium">Step 1: Retrieve session tokens & symbol dependencies</span>
                    </div>
                    <span className="text-[10px] text-[var(--forge-text-muted)]">0.4s</span>
                  </div>

                  <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-2.5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[var(--forge-success)] shrink-0" />
                      <span className="text-[var(--forge-text-primary)] font-medium">Step 2: Tree-sitter AST symbol resolution on SqlSessionRepository</span>
                    </div>
                    <span className="text-[10px] text-[var(--forge-text-muted)]">1.2s</span>
                  </div>

                  <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-2.5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Terminal className="h-3.5 w-3.5 text-[var(--forge-success)] shrink-0" />
                      <span className="text-[var(--forge-text-primary)] font-medium">Tool: terminal.execute &quot;python -m pytest tests/test_session.py&quot;</span>
                    </div>
                    <span className="text-[10px] text-[var(--forge-text-muted)]">2.1s</span>
                  </div>

                  <div className="rounded border border-[var(--forge-warning-border)] bg-[var(--forge-warning-surface)] p-2.5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="h-3.5 w-3.5 text-[var(--forge-warning)] shrink-0" />
                      <span className="text-[var(--forge-warning)] font-medium">Tool: file.modify (src/auth/session_service.py) — Suspended</span>
                    </div>
                    <span className="text-[10px] font-semibold text-[var(--forge-warning)]">WAITING_FOR_APPROVAL</span>
                  </div>
                </div>
              )}

              {previewTab === 'files' && (
                <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] divide-y divide-[var(--forge-border-subtle)] font-mono text-xs">
                  <div className="p-2.5 flex items-center justify-between">
                    <span className="text-[var(--forge-text-primary)]">services/api/src/forge_api/application/auth/session_service.py</span>
                    <span className="text-[var(--forge-success)]">+156 -23</span>
                  </div>
                  <div className="p-2.5 flex items-center justify-between">
                    <span className="text-[var(--forge-text-primary)]">services/api/src/forge_api/infrastructure/security/hasher.py</span>
                    <span className="text-[var(--forge-success)]">+87 -12</span>
                  </div>
                  <div className="p-2.5 flex items-center justify-between">
                    <span className="text-[var(--forge-text-primary)]">services/api/tests/test_session_hardening.py</span>
                    <span className="text-[var(--forge-success)]">+199</span>
                  </div>
                </div>
              )}

              {previewTab === 'diff' && (
                <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-3 font-mono text-xs overflow-x-auto select-text leading-5">
                  <div className="text-[var(--forge-text-muted)] text-[11px] pb-1 border-b border-[var(--forge-border-subtle)] mb-2">
                    @@ -42,7 +42,12 @@ def verify_refresh_token(self, token: str) -&gt; TokenClaims:
                  </div>
                  <div className="text-[var(--forge-danger)] bg-[var(--forge-danger-surface)] px-1 rounded">
                    -    return self._token_encoder.decode_unsafe(token)
                  </div>
                  <div className="text-[var(--forge-success)] bg-[var(--forge-success-surface)] px-1 rounded">
                    +    claims = self._token_encoder.decode(token)
                  </div>
                  <div className="text-[var(--forge-success)] bg-[var(--forge-success-surface)] px-1 rounded">
                    +    if self._revocation_store.is_revoked(claims.session_id):
                  </div>
                  <div className="text-[var(--forge-success)] bg-[var(--forge-success-surface)] px-1 rounded">
                    {'+ raise SessionRevokedError(f"Session {claims.session_id} is revoked")'}
                  </div>
                  <div className="text-[var(--forge-success)] bg-[var(--forge-success-surface)] px-1 rounded">
                    +    return claims
                  </div>
                </div>
              )}
            </div>

            {/* Right Telemetry Column */}
            <div className="w-full lg:w-64 shrink-0 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-3.5 space-y-3 text-xs font-mono">
              <div className="flex items-center justify-between pb-2 border-b border-[var(--forge-border-subtle)]">
                <span className="text-[var(--forge-text-muted)] uppercase text-[10px]">Usage & Accounting</span>
                <span className="text-[var(--forge-success)] font-semibold">$0.045</span>
              </div>

              <div className="space-y-1.5 text-[11px]">
                <div className="flex justify-between text-[var(--forge-text-secondary)]">
                  <span>LLM Calls:</span>
                  <span className="text-[var(--forge-text-primary)] font-semibold">4 / 30</span>
                </div>
                <div className="flex justify-between text-[var(--forge-text-secondary)]">
                  <span>Tool Invocations:</span>
                  <span className="text-[var(--forge-text-primary)] font-semibold">6 / 50</span>
                </div>
                <div className="flex justify-between text-[var(--forge-text-secondary)]">
                  <span>Input Tokens:</span>
                  <span className="text-[var(--forge-text-primary)]">4,200</span>
                </div>
                <div className="flex justify-between text-[var(--forge-text-secondary)]">
                  <span>Output Tokens:</span>
                  <span className="text-[var(--forge-text-primary)]">850</span>
                </div>
                <div className="flex justify-between text-[var(--forge-text-secondary)] pt-1 border-t border-[var(--forge-border-subtle)]">
                  <span>Wall Clock Limit:</span>
                  <span className="text-[var(--forge-text-primary)]">900s</span>
                </div>
              </div>

              <div className="pt-2 border-t border-[var(--forge-border-subtle)] space-y-1 text-[10px] text-[var(--forge-text-muted)]">
                <div>Arg Hash: SHA-256 Verified</div>
                <div>Sandbox: Untrusted Path Contained</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof / Engineering Proof Section */}
      <section className="border-y border-[var(--forge-border)] bg-[var(--forge-surface)] py-12 px-4 sm:px-8">
        <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          <div className="space-y-1">
            <p className="text-2xl sm:text-3xl font-bold font-mono text-[var(--forge-text-primary)]">
              100%
            </p>
            <p className="text-xs text-[var(--forge-text-secondary)] font-medium">
              Repository-Aware AST Intelligence
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-2xl sm:text-3xl font-bold font-mono text-[var(--forge-text-primary)]">
              50 Max
            </p>
            <p className="text-xs text-[var(--forge-text-secondary)] font-medium">
              Bounded Tool Executions Per Session
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-2xl sm:text-3xl font-bold font-mono text-[var(--forge-text-primary)]">
              0
            </p>
            <p className="text-xs text-[var(--forge-text-secondary)] font-medium">
              Unauthorized File Modifications
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-2xl sm:text-3xl font-bold font-mono text-[var(--forge-text-primary)]">
              8,192
            </p>
            <p className="text-xs text-[var(--forge-text-secondary)] font-medium">
              Token Ranked Context Windows
            </p>
          </div>
        </div>
      </section>

      {/* Core Capabilities (Asymmetrical Compositions) */}
      <section id="capabilities" className="py-20 px-4 sm:px-8 max-w-6xl mx-auto w-full space-y-16">
        <div className="space-y-2 max-w-2xl">
          <span className="text-[11px] font-mono uppercase tracking-wider text-[var(--forge-accent)] font-semibold">
            Architectural Excellence
          </span>
          <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-[var(--forge-text-primary)]">
            Built for engineering constraints, not conversational parlor tricks.
          </h2>
        </div>

        {/* Feature 1: Split Layout — Agent Orchestrator & Safety */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          <div className="space-y-4">
            <div className="h-9 w-9 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-accent)]">
              <Bot className="h-5 w-5" />
            </div>
            <h3 className="text-lg sm:text-xl font-semibold text-[var(--forge-text-primary)]">
              Durable Bounded Execution Loop
            </h3>
            <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] leading-relaxed">
              Forge agents formulate multi-step plans executed through strict Clean Architecture workers. Hard limits prevent runaway token drain: 900 seconds maximum wall time, 30 LLM calls, and 50 tool invocations. The state machine suspends safely when requiring approval and resumes on command.
            </p>
            <ul className="space-y-2 text-xs text-[var(--forge-text-secondary)]">
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Zero infinite loops: 51st tool call or 31st LLM call strictly rejected</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Live Redis Pub/Sub event handoff with 500-event replay buffer</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Cryptographic HMAC verification before resuming human-in-the-loop tasks</span>
              </li>
            </ul>
          </div>

          <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-4 font-mono text-xs text-[var(--forge-text-secondary)] space-y-2">
            <div className="text-[10px] text-[var(--forge-text-muted)] border-b border-[var(--forge-border-subtle)] pb-2 uppercase">
              Agent State Transitions
            </div>
            <div className="text-[var(--forge-text-primary)]">CREATED → PLANNING → RUNNING</div>
            <div className="text-[var(--forge-warning)] pl-4">↳ WAITING_FOR_APPROVAL (Suspended)</div>
            <div className="text-[var(--forge-success)] pl-8">↳ GRANTED (Arg HMAC verified) → RUNNING</div>
            <div className="text-[var(--forge-success)]">→ COMPLETED (Metrics & artifacts saved)</div>
          </div>
        </div>

        {/* Feature 2: Split Layout — Codebase Intelligence & AST */}
        <div id="intelligence" className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-4 font-mono text-xs text-[var(--forge-text-secondary)] space-y-2 order-2 md:order-1">
            <div className="text-[10px] text-[var(--forge-text-muted)] border-b border-[var(--forge-border-subtle)] pb-2 uppercase">
              Tree-sitter Symbol Resolution
            </div>
            <div className="text-[var(--forge-accent)]">def parse_repository_symbols(repo_id: str):</div>
            <div className="pl-4 text-[var(--forge-text-muted)]"># Multi-language AST: Python, TypeScript, Rust, Go</div>
            <div className="pl-4 text-[var(--forge-text-secondary)]">symbols = tree_sitter.extract_declarations(path)</div>
            <div className="pl-4 text-[var(--forge-text-secondary)]">deps = dependency_resolver.resolve_imports(path)</div>
            <div className="pl-4 text-[var(--forge-success)]">return pgvector.store_chunks(symbols, dims=384)</div>
          </div>

          <div className="space-y-4 order-1 md:order-2">
            <div className="h-9 w-9 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-accent)]">
              <Code2 className="h-5 w-5" />
            </div>
            <h3 className="text-lg sm:text-xl font-semibold text-[var(--forge-text-primary)]">
              Repository-Aware Codebase Intelligence
            </h3>
            <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] leading-relaxed">
              No blind prompting. Forge reads your codebase using Tree-sitter parsers across TypeScript, Python, Rust, and Go. Symbol graphs trace function declarations and dependencies, enabling surgical semantic search over pgvector embeddings without hallucinated imports.
            </p>
            <ul className="space-y-2 text-xs text-[var(--forge-text-secondary)]">
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Deterministic Tree-sitter parsing: classes, methods, and types</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Incremental content-hash re-indexing only changes affected files</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Post-index memory staleness invalidation preserves factual truth</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Feature 3: Safety & Human-in-the-Loop */}
        <div id="safety" className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          <div className="space-y-4">
            <div className="h-9 w-9 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-warning)]">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="text-lg sm:text-xl font-semibold text-[var(--forge-text-primary)]">
              Cryptographic Human Authorization
            </h3>
            <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] leading-relaxed">
              Every dangerous operation—including file modifications, file deletions, and terminal executions—is subject to Forge&apos;s Policy Engine. Critical tools pause the execution loop until you review the exact target path, unified diff, and execution reason.
            </p>
            <ul className="space-y-2 text-xs text-[var(--forge-text-secondary)]">
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Canonical SHA-256 argument hash verifies zero argument tampering</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Untrusted path containment blocks directory traversal escapes</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-[var(--forge-success)]" />
                <span>Automated secret scrubbing prevents API key leakage in audit logs</span>
              </li>
            </ul>
          </div>

          <div className="rounded-lg border border-[var(--forge-warning-border)] bg-[var(--forge-surface)] p-4 space-y-3">
            <div className="flex items-center justify-between text-xs border-b border-[var(--forge-border-subtle)] pb-2">
              <span className="font-semibold text-[var(--forge-warning)]">Policy Engine Evaluation</span>
              <span className="font-mono text-[10px] text-[var(--forge-text-muted)]">RISK: HIGH</span>
            </div>
            <div className="font-mono text-xs space-y-1 text-[var(--forge-text-secondary)]">
              <div>Requested: <span className="text-[var(--forge-text-primary)]">file.modify</span></div>
              <div>Target: <span className="text-[var(--forge-accent)]">apps/web/src/auth/service.ts</span></div>
              <div>Decision: <span className="text-[var(--forge-warning)] font-bold">SUSPEND_FOR_HUMAN_APPROVAL</span></div>
            </div>
          </div>
        </div>
      </section>

      {/* Developer Workflow Timeline */}
      <section id="workflow" className="border-t border-[var(--forge-border)] bg-[var(--forge-surface)] py-20 px-4 sm:px-8">
        <div className="max-w-6xl mx-auto space-y-12">
          <div className="text-center space-y-2 max-w-2xl mx-auto">
            <span className="text-[11px] font-mono uppercase tracking-wider text-[var(--forge-accent)] font-semibold">
              The Engineering Lifecycle
            </span>
            <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-[var(--forge-text-primary)]">
              From task objective to verified diff in five disciplined steps.
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-4 space-y-2">
              <span className="font-mono text-xs font-bold text-[var(--forge-accent)]">01. INSTRUCTION</span>
              <h4 className="text-xs font-semibold text-[var(--forge-text-primary)]">Define Task</h4>
              <p className="text-[11px] text-[var(--forge-text-secondary)] leading-relaxed">
                Provide a natural language engineering task with bounded scope and expected outcomes.
              </p>
            </div>

            <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-4 space-y-2">
              <span className="font-mono text-xs font-bold text-[var(--forge-accent)]">02. RESOLUTION</span>
              <h4 className="text-xs font-semibold text-[var(--forge-text-primary)]">Context Assembly</h4>
              <p className="text-[11px] text-[var(--forge-text-secondary)] leading-relaxed">
                Tree-sitter AST queries and pgvector cosine search assemble an 8,192 token prompt.
              </p>
            </div>

            <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-4 space-y-2">
              <span className="font-mono text-xs font-bold text-[var(--forge-accent)]">03. PLANNING</span>
              <h4 className="text-xs font-semibold text-[var(--forge-text-primary)]">Plan Generation</h4>
              <p className="text-[11px] text-[var(--forge-text-secondary)] leading-relaxed">
                The agent generates a structured step-by-step plan before invoking any tools.
              </p>
            </div>

            <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-4 space-y-2">
              <span className="font-mono text-xs font-bold text-[var(--forge-warning)]">04. APPROVAL</span>
              <h4 className="text-xs font-semibold text-[var(--forge-text-primary)]">Human Review</h4>
              <p className="text-[11px] text-[var(--forge-text-secondary)] leading-relaxed">
                High-risk file modifications or terminal commands suspend until authorized.
              </p>
            </div>

            <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-4 space-y-2">
              <span className="font-mono text-xs font-bold text-[var(--forge-success)]">05. DIFF REVIEW</span>
              <h4 className="text-xs font-semibold text-[var(--forge-text-primary)]">Verification</h4>
              <p className="text-[11px] text-[var(--forge-text-secondary)] leading-relaxed">
                Review unified diffs with line counts, inspect test execution, and merge with confidence.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section className="py-24 px-4 sm:px-8 max-w-4xl mx-auto w-full text-center space-y-6">
        <h2 className="text-3xl sm:text-5xl font-bold tracking-tight text-[var(--forge-text-primary)]">
          Autonomous engineering with complete developer control.
        </h2>
        <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] max-w-xl mx-auto leading-relaxed">
          Launch your first agent in seconds. Inspect code, run tests, and review diffs without giving up architectural control.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href={`/workspaces/${demoWorkspaceId}/agents/new`}
            className="inline-flex items-center gap-2 rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-5 py-2.5 text-xs sm:text-sm font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors"
          >
            <span>Start building for free</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href={`/workspaces/${demoWorkspaceId}/agents`}
            className="inline-flex items-center gap-2 rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] hover:border-[var(--forge-border-highlight)] hover:bg-[var(--forge-surface-secondary)] px-4 py-2.5 text-xs sm:text-sm font-medium text-[var(--forge-text-primary)] transition-colors"
          >
            <span>View Workspace</span>
          </Link>
        </div>
      </section>

      {/* Clean Footer */}
      <footer className="border-t border-[var(--forge-border)] bg-[var(--forge-surface)] py-8 px-4 sm:px-8 mt-auto text-xs text-[var(--forge-text-muted)]">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <ForgeLogo size="sm" showTagline={false} />
            <span className="font-mono text-[10px] tracking-wider uppercase text-[var(--forge-text-muted)]">
              BUILD BETTER. SHIP FASTER.
            </span>
          </div>

          <div className="flex items-center gap-5 text-xs">
            <a href="https://github.com/paradkarharsh/forge" target="_blank" rel="noopener noreferrer" className="hover:text-[var(--forge-text-primary)] transition-colors">
              GitHub
            </a>
            <Link href={`/workspaces/${demoWorkspaceId}/agents`} className="hover:text-[var(--forge-text-primary)] transition-colors">
              Workspace
            </Link>
            <span className="text-[11px] font-mono">
              © {new Date().getFullYear()} Forge. Clean Architecture AI Engineering.
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
