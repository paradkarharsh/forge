'use client';

import { Bot, FolderGit2, Layers } from 'lucide-react';
import Link from 'next/link';

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
    <nav className="h-14 border-b border-zinc-800 bg-zinc-950 px-4 sm:px-6 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-sm font-bold tracking-tight text-zinc-100 hover:text-indigo-400 transition-colors"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white font-mono text-xs font-black shadow-xs">
            F
          </div>
          <span>Forge</span>
        </Link>

        <div className="h-4 w-px bg-zinc-800 hidden sm:block" />

        <div className="flex items-center gap-1 text-xs font-medium">
          <Link
            href={`/workspaces/${workspaceId}`}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 transition-colors"
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Workspace</span>
          </Link>

          {repositoryId && (
            <Link
              href={`/workspaces/${workspaceId}/repositories/${repositoryId}`}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 transition-colors"
            >
              <FolderGit2 className="h-3.5 w-3.5" />
              <span>Repository</span>
            </Link>
          )}

          <Link
            href={agentsHref}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 font-semibold transition-colors"
          >
            <Bot className="h-3.5 w-3.5" />
            <span>Agents</span>
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-zinc-500 font-mono">
        <span className="hidden sm:inline">Workspace {workspaceId.slice(0, 8)}</span>
      </div>
    </nav>
  );
}
