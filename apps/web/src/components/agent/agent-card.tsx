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
      className="group block rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 transition-colors hover:border-[var(--forge-border-highlight)] hover:bg-[var(--forge-surface-secondary)] shadow-xs"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="space-y-1 min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-xs sm:text-sm font-semibold text-[var(--forge-text-primary)] group-hover:text-[var(--forge-accent)] transition-colors truncate">
              {session.objective}
            </h3>
            <AgentStatusBadge status={session.status} size="sm" />
          </div>

          <div className="flex items-center gap-3 text-[11px] text-[var(--forge-text-muted)] font-mono flex-wrap">
            {targetRepoId && (
              <span className="inline-flex items-center gap-1">
                <GitBranch className="h-3 w-3" />
                <span>Repo {targetRepoId.slice(0, 8)}</span>
              </span>
            )}

            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span>{formatRelativeTime(session.created_at)}</span>
            </span>

            {session.metrics.wall_time_seconds > 0 && (
              <span>Duration: {formatDuration(session.metrics.wall_time_seconds)}</span>
            )}

            {isActive && (
              <span className="text-[var(--forge-success)] font-medium">
                Active
              </span>
            )}
          </div>
        </div>

        {/* Right side stats */}
        <div className="flex items-center gap-4 text-xs font-mono text-[var(--forge-text-secondary)] shrink-0 self-end sm:self-center">
          <div className="flex items-center gap-3">
            <span
              className="inline-flex items-center gap-1"
              title="Total LLM calls"
            >
              <Cpu className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
              <span>{session.metrics.total_llm_calls}</span>
            </span>
            <span
              className="inline-flex items-center gap-1"
              title="Total tool calls"
            >
              <Wrench className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
              <span>{session.metrics.total_tool_calls}</span>
            </span>
          </div>

          <ChevronRight className="h-4 w-4 text-[var(--forge-text-muted)] group-hover:text-[var(--forge-text-primary)] group-hover:translate-x-0.5 transition-all" />
        </div>
      </div>
    </Link>
  );
}
