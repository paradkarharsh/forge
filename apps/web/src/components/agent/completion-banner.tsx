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
      className="mb-6 rounded-xl border border-emerald-500/30 bg-gradient-to-b from-emerald-950/20 via-neutral-900 to-neutral-900/90 p-5 shadow-xl shadow-emerald-950/20"
    >
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start space-x-3.5">
          <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-400 ring-1 ring-emerald-500/30">
            <CheckCircle2 className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-semibold text-white">
                Task Execution Completed
              </h3>
              <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-emerald-300 border border-emerald-500/30">
                Success
              </span>
            </div>
            <p className="mt-1 text-xs text-neutral-300 max-w-2xl line-clamp-2">
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
                  className="inline-flex items-center space-x-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-200 hover:bg-neutral-700 hover:text-white transition-colors"
                >
                  <FileCode className="h-3.5 w-3.5" />
                  <span>Changed Files ({changedFilesCount})</span>
                </button>
              )}
              {onOpenDiff && (
                <button
                  type="button"
                  onClick={onOpenDiff}
                  className="inline-flex items-center space-x-1.5 rounded-lg border border-emerald-500/40 bg-emerald-950/30 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-900/50 transition-colors"
                >
                  <GitCommit className="h-3.5 w-3.5" />
                  <span>Review Diff</span>
                </button>
              )}
            </>
          )}

          <Link
            href={newAgentHref}
            className="inline-flex items-center space-x-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 shadow-md transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Launch Another Agent</span>
          </Link>
        </div>
      </div>

      {/* Metrics Summary Grid */}
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4 rounded-lg border border-neutral-800 bg-neutral-950/60 p-3 text-xs">
        <div>
          <span className="text-neutral-500">Execution Time:</span>
          <p className="font-mono font-medium text-neutral-200 mt-0.5">
            {metrics ? `${metrics.wall_time_seconds.toFixed(1)}s` : '0.0s'}
          </p>
        </div>
        <div>
          <span className="text-neutral-500">Steps / Tools:</span>
          <p className="font-mono font-medium text-neutral-200 mt-0.5">
            {session.current_step} steps / {metrics?.total_tool_calls || 0} tools
          </p>
        </div>
        <div>
          <span className="text-neutral-500">Tokens:</span>
          <p className="font-mono font-medium text-neutral-200 mt-0.5">
            {metrics ? formatTokens(metrics.total_input_tokens + metrics.total_output_tokens) : '0'}
          </p>
        </div>
        <div>
          <span className="text-neutral-500">Estimated Cost:</span>
          <p className="font-mono font-medium text-emerald-400 mt-0.5">
            {metrics ? formatCost(metrics.estimated_cost_usd) : '$0.00'}
          </p>
        </div>
      </div>

      <div className="mt-3 flex justify-end">
        <Link
          href={backHref}
          className="inline-flex items-center space-x-1 text-xs text-neutral-400 hover:text-neutral-200 transition-colors"
        >
          <span>Return to agent list</span>
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
