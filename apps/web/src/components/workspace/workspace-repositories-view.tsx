'use client';

import React from 'react';
import Link from 'next/link';
import {
  Bot,
  CheckCircle2,
  FolderGit2,
  GitBranch,
  Plus,
} from 'lucide-react';
import { AppShell } from '@/components/layout/app-shell';

interface WorkspaceRepositoriesViewProps {
  readonly workspaceId: string;
}

export function WorkspaceRepositoriesView({
  workspaceId,
}: WorkspaceRepositoriesViewProps) {
  return (
    <AppShell workspaceId={workspaceId}>
      <div className="max-w-6xl w-full mx-auto p-4 sm:p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-0.5">
            <h1 className="text-xl font-semibold tracking-tight text-[var(--forge-text-primary)]">
              Workspace Repositories
            </h1>
            <p className="text-xs text-[var(--forge-text-secondary)]">
              Onboarded codebases indexed with Tree-sitter AST parsing and vector embeddings.
            </p>
          </div>

          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-3.5 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors self-start sm:self-auto"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Connect Repository</span>
          </button>
        </div>

        {/* Repository Cards */}
        <div className="space-y-3">
          <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-text-muted)]">
                  <FolderGit2 className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold font-mono text-[var(--forge-text-primary)]">
                    forge
                  </h3>
                  <div className="flex items-center gap-3 text-[11px] text-[var(--forge-text-muted)] font-mono">
                    <span className="flex items-center gap-1">
                      <GitBranch className="h-3 w-3" />
                      <span>main</span>
                    </span>
                    <span>Clean Architecture monorepo</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                <span className="inline-flex items-center gap-1 rounded bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)] px-2 py-0.5 text-[10px] font-mono font-medium">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Tree-sitter Indexed</span>
                </span>
                <Link
                  href={`/workspaces/${workspaceId}/repositories/forge/agents`}
                  className="inline-flex items-center gap-1 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] hover:border-[var(--forge-border-highlight)] px-2.5 py-1 text-xs font-medium text-[var(--forge-text-primary)] transition-colors"
                >
                  <Bot className="h-3.5 w-3.5 text-[var(--forge-accent)]" />
                  <span>View Agents</span>
                </Link>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-[var(--forge-border-subtle)] text-xs font-mono">
              <div>
                <span className="text-[10px] text-[var(--forge-text-muted)] uppercase block">Languages</span>
                <span className="text-[var(--forge-text-secondary)]">TypeScript, Python</span>
              </div>
              <div>
                <span className="text-[10px] text-[var(--forge-text-muted)] uppercase block">Symbols Parsed</span>
                <span className="text-[var(--forge-text-secondary)]">AST Graph Active</span>
              </div>
              <div>
                <span className="text-[10px] text-[var(--forge-text-muted)] uppercase block">Semantic Search</span>
                <span className="text-[var(--forge-success)]">pgvector (384d)</span>
              </div>
              <div>
                <span className="text-[10px] text-[var(--forge-text-muted)] uppercase block">Index Status</span>
                <span className="text-[var(--forge-text-secondary)]">Up to date</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
