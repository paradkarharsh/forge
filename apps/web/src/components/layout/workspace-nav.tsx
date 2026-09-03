'use client';

import { Bot, FolderGit2, Layers } from 'lucide-react';
import Link from 'next/link';
import { ForgeLogo } from '../brand/forge-logo';
import { ThemeToggle } from '../theme/theme-toggle';

interface WorkspaceNavProps {
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
}

export function WorkspaceNav({
  workspaceId,
  repositoryId,
}: WorkspaceNavProps) {
  const agentsHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents`
    : `/workspaces/${workspaceId}/agents`;

  return (
    <nav className="h-12 border-b border-[var(--forge-border)] bg-[var(--forge-surface)] px-4 sm:px-6 flex items-center justify-between">
      <div className="flex items-center gap-5">
        <Link
          href="/"
          className="flex items-center hover:opacity-90 transition-opacity"
        >
          <ForgeLogo size="sm" />
        </Link>

        <div className="h-4 w-px bg-[var(--forge-border)] hidden sm:block" />

        <div className="flex items-center gap-1 text-xs font-medium">
          <Link
            href={`/workspaces/${workspaceId}`}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:bg-[var(--forge-surface-secondary)] transition-colors"
          >
            <Layers className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
            <span>Workspace</span>
          </Link>

          {repositoryId && (
            <Link
              href={`/workspaces/${workspaceId}/repositories/${repositoryId}`}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:bg-[var(--forge-surface-secondary)] transition-colors"
            >
              <FolderGit2 className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
              <span>Repository</span>
            </Link>
          )}

          <Link
            href={agentsHref}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[var(--forge-text-primary)] bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] font-semibold transition-colors"
          >
            <Bot className="h-3.5 w-3.5 text-[var(--forge-accent)]" />
            <span>Agents</span>
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs font-mono">
        <span className="text-[var(--forge-text-muted)] hidden sm:inline">
          ws-{workspaceId.slice(0, 8)}
        </span>
        <ThemeToggle />
      </div>
    </nav>
  );
}
