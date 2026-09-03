'use client';

import {
  ChevronRight,
  Clock,
  Cpu,
  GitBranch,
  Wrench,
} from 'lucide-react';
import Link from 'next/link';
import type { AgentSession } from '../../lib/api/types';
import {
  formatDuration,
  formatRelativeTime,
} from '../../lib/utils/formatters';
import { AgentStatusBadge } from './agent-status-badge';

interface AgentCardProps {
  readonly session: AgentSession;
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
}

export function AgentCard({
  session,
  workspaceId,
  repositoryId,
}: AgentCardProps) {
  const targetRepoId = repositoryId || session.repository_id;
  const href = targetRepoId
    ? `/workspaces/${workspaceId}/repositories/${targetRepoId}/agents/${session.id}`
    : `/workspaces/${workspaceId}/agents/${session.id}`;

  const isActive = session.status === 'planning' || session.status === 'running';

  return (
    <Link
      href={href}
      className="group block rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4 transition-all duration-150 hover:border-zinc-700 hover:bg-zinc-900/40 shadow-xs"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1.5 min-w-0 flex-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h3 className="text-sm sm:text-base font-semibold text-zinc-200 group-hover:text-indigo-300 transition-colors truncate">
              {session.objective}
            </h3>
            <AgentStatusBadge status={session.status} size="sm" />
          </div>

          <div className="flex items-center gap-3 text-xs text-zinc-400 font-mono flex-wrap">
            {targetRepoId && (
              <span className="inline-flex items-center gap-1 text-zinc-400">
                <GitBranch className="h-3 w-3 text-zinc-500" />
                <span>Repo {targetRepoId.slice(0, 8)}</span>
              </span>
            )}

            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3 text-zinc-500" />
              <span>{formatRelativeTime(session.created_at)}</span>
            </span>

            {session.metrics.wall_time_seconds > 0 && (
              <span>Duration: {formatDuration(session.metrics.wall_time_seconds)}</span>
            )}

            {isActive && (
              <span className="text-indigo-400 font-medium animate-pulse">
                Active execution
              </span>
            )}
          </div>
        </div>

        {/* Right side stats */}
        <div className="flex items-center gap-4 text-xs font-mono text-zinc-400 shrink-0 self-end sm:self-center">
          <div className="flex items-center gap-3">
            <span
              className="inline-flex items-center gap-1"
              title="Total LLM calls"
            >
              <Cpu className="h-3.5 w-3.5 text-zinc-500" />
              <span>{session.metrics.total_llm_calls}</span>
            </span>
            <span
              className="inline-flex items-center gap-1"
              title="Total tool calls"
            >
              <Wrench className="h-3.5 w-3.5 text-zinc-500" />
              <span>{session.metrics.total_tool_calls}</span>
            </span>
          </div>

          <ChevronRight className="h-4 w-4 text-zinc-600 group-hover:text-zinc-300 group-hover:translate-x-0.5 transition-all" />
        </div>
      </div>
    </Link>
  );
}
