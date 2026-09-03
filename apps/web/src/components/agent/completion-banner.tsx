'use client';

import React from 'react';
import Link from 'next/link';
import { CheckCircle2, FileCode, GitCommit, ArrowRight, RotateCcw } from 'lucide-react';
import type { AgentSession } from '../../lib/api/types';
import { formatCost, formatTokens } from '../../lib/utils/formatters';

interface CompletionBannerProps {
  readonly session: AgentSession;
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
  readonly changedFilesCount: number;
  readonly onReviewChanges?: () => void;
  readonly onOpenDiff?: () => void;
}

export function CompletionBanner({
  session,
  workspaceId,
  repositoryId,
  changedFilesCount,
  onReviewChanges,
  onOpenDiff,
}: CompletionBannerProps) {
  const metrics = session.metrics;
  const newAgentHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents/new`
    : `/workspaces/${workspaceId}/agents/new`;

  const backHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents`
    : `/workspaces/${workspaceId}/agents`;

  return (
    <div
      role="region"
      aria-label="Agent Execution Completed"
      className="mb-6 rounded-lg border border-[var(--forge-success-border)] bg-[var(--forge-surface)] p-4 shadow-xs"
    >
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start space-x-3">
          <div className="rounded-md bg-[var(--forge-success-surface)] p-2 text-[var(--forge-success)] border border-[var(--forge-success-border)]">
            <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-semibold text-[var(--forge-text-primary)]">
                Task Execution Completed
              </h3>
              <span className="rounded bg-[var(--forge-success-surface)] px-1.5 py-0.2 text-[10px] font-semibold uppercase tracking-wider text-[var(--forge-success)] border border-[var(--forge-success-border)]">
                Success
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--forge-text-secondary)] max-w-2xl line-clamp-2">
              {session.objective}
            </p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          {changedFilesCount > 0 && (
            <>
              {onReviewChanges && (
                <button
                  type="button"
                  onClick={onReviewChanges}
                  className="inline-flex items-center space-x-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2.5 py-1.5 text-xs font-medium text-[var(--forge-text-primary)] hover:border-[var(--forge-border-highlight)] transition-colors"
                >
                  <FileCode className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
                  <span>Changed Files ({changedFilesCount})</span>
                </button>
              )}
              {onOpenDiff && (
                <button
                  type="button"
                  onClick={onOpenDiff}
                  className="inline-flex items-center space-x-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2.5 py-1.5 text-xs font-medium text-[var(--forge-success)] hover:border-[var(--forge-success-border)] transition-colors"
                >
                  <GitCommit className="h-3.5 w-3.5" />
                  <span>Review Diff</span>
                </button>
              )}
            </>
          )}

          <Link
            href={newAgentHref}
            className="inline-flex items-center space-x-1.5 rounded bg-[var(--forge-accent)] px-3 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] hover:bg-[var(--forge-accent-hover)] transition-colors shadow-xs"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Launch Another Agent</span>
          </Link>
        </div>
      </div>

      {/* Metrics Summary Grid */}
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-2.5 text-xs">
        <div>
          <span className="text-[var(--forge-text-muted)]">Execution Time:</span>
          <p className="font-mono font-medium text-[var(--forge-text-primary)] mt-0.5">
            {metrics ? `${metrics.wall_time_seconds.toFixed(1)}s` : '0.0s'}
          </p>
        </div>
        <div>
          <span className="text-[var(--forge-text-muted)]">Steps / Tools:</span>
          <p className="font-mono font-medium text-[var(--forge-text-primary)] mt-0.5">
            {session.current_step} steps / {metrics?.total_tool_calls || 0} tools
          </p>
        </div>
        <div>
          <span className="text-[var(--forge-text-muted)]">Tokens:</span>
          <p className="font-mono font-medium text-[var(--forge-text-primary)] mt-0.5">
            {metrics ? formatTokens(metrics.total_input_tokens + metrics.total_output_tokens) : '0'}
          </p>
        </div>
        <div>
          <span className="text-[var(--forge-text-muted)]">Estimated Cost:</span>
          <p className="font-mono font-medium text-[var(--forge-success)] mt-0.5">
            {metrics ? formatCost(metrics.estimated_cost_usd) : '$0.00'}
          </p>
        </div>
      </div>

      <div className="mt-2.5 flex justify-end">
        <Link
          href={backHref}
          className="inline-flex items-center space-x-1 text-xs text-[var(--forge-text-muted)] hover:text-[var(--forge-text-secondary)] transition-colors"
        >
          <span>Return to agent list</span>
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
