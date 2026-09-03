'use client';

import React from 'react';
import Link from 'next/link';
import { AlertOctagon, RotateCcw, ArrowRight, FileCode } from 'lucide-react';
import type { AgentSession } from '../../lib/api/types';

interface FailureBannerProps {
  readonly session: AgentSession;
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
  readonly changedFilesCount?: number;
  readonly onReviewChanges?: () => void;
}

/**
 * Sanitize error message to prevent leaking Python traces or database internals.
 */
function sanitizeErrorMessage(rawMessage?: string | null): string {
  if (!rawMessage) return 'Execution was stopped due to an unrecoverable failure.';
  // Strip Traceback blocks
  if (rawMessage.includes('Traceback (most recent call last):')) {
    const lines = rawMessage.split('\n');
    const lastLine = lines[lines.length - 1] || lines[lines.length - 2] || 'Internal execution error';
    return lastLine.replace(/^[\w.]*Error:\s*/, '');
  }
  return rawMessage;
}

export function FailureBanner({
  session,
  workspaceId,
  repositoryId,
  changedFilesCount = 0,
  onReviewChanges,
}: FailureBannerProps) {
  const isTimeout = session.status === 'timed_out';
  const isExpired = session.status === 'expired';

  const title = isTimeout
    ? 'Execution Timed Out'
    : isExpired
    ? 'Approval Expired'
    : 'Execution Failed';

  const statusLabel = isTimeout ? 'Timed Out' : isExpired ? 'Expired' : 'Failed';

  const newAgentHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents/new`
    : `/workspaces/${workspaceId}/agents/new`;

  const backHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents`
    : `/workspaces/${workspaceId}/agents`;

  const safeError = sanitizeErrorMessage(session.failure_reason);

  return (
    <div
      role="alert"
      aria-label={title}
      className="mb-6 rounded-xl border border-rose-500/40 bg-gradient-to-b from-rose-950/20 via-neutral-900 to-neutral-900/90 p-5 shadow-xl shadow-rose-950/20"
    >
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start space-x-3.5">
          <div className="rounded-lg bg-rose-500/10 p-2 text-rose-400 ring-1 ring-rose-500/30">
            <AlertOctagon className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-semibold text-white">{title}</h3>
              <span className="rounded bg-rose-500/20 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-rose-300 border border-rose-500/30">
                {statusLabel}
              </span>
            </div>
            <p className="mt-1 text-xs text-rose-200/90 font-mono max-w-2xl">
              {safeError}
            </p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          {changedFilesCount > 0 && onReviewChanges && (
            <button
              type="button"
              onClick={onReviewChanges}
              className="inline-flex items-center space-x-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-200 hover:bg-neutral-700 transition-colors"
            >
              <FileCode className="h-3.5 w-3.5" />
              <span>Review Partial Changes ({changedFilesCount})</span>
            </button>
          )}

          <Link
            href={newAgentHref}
            className="inline-flex items-center space-x-1.5 rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-rose-500 shadow-md transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Launch New Agent</span>
          </Link>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-neutral-800/80 pt-3 text-xs">
        <span className="text-neutral-500">
          Last recorded execution step: <span className="text-neutral-300 font-mono">Step {session.current_step}</span>
        </span>
        <Link
          href={backHref}
          className="inline-flex items-center space-x-1 text-neutral-400 hover:text-neutral-200 transition-colors"
        >
          <span>Return to agent list</span>
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
