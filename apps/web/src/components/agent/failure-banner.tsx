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
      className="mb-6 rounded-lg border border-[var(--forge-danger-border)] bg-[var(--forge-surface)] p-4 shadow-xs"
    >
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start space-x-3">
          <div className="rounded-md bg-[var(--forge-danger-surface)] p-2 text-[var(--forge-danger)] border border-[var(--forge-danger-border)]">
            <AlertOctagon className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-semibold text-[var(--forge-text-primary)]">{title}</h3>
              <span className="rounded bg-[var(--forge-danger-surface)] px-1.5 py-0.2 text-[10px] font-semibold uppercase tracking-wider text-[var(--forge-danger)] border border-[var(--forge-danger-border)]">
                {statusLabel}
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--forge-danger)] font-mono max-w-2xl">
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
              className="inline-flex items-center space-x-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2.5 py-1.5 text-xs font-medium text-[var(--forge-text-primary)] hover:border-[var(--forge-border-highlight)] transition-colors"
            >
              <FileCode className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
              <span>Review Partial Changes ({changedFilesCount})</span>
            </button>
          )}

          <Link
            href={newAgentHref}
            className="inline-flex items-center space-x-1.5 rounded bg-[var(--forge-accent)] px-3 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] hover:bg-[var(--forge-accent-hover)] shadow-xs transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Launch New Agent</span>
          </Link>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-[var(--forge-border)] pt-2.5 text-xs">
        <span className="text-[var(--forge-text-muted)]">
          Last recorded execution step: <span className="text-[var(--forge-text-primary)] font-mono">Step {session.current_step}</span>
        </span>
        <Link
          href={backHref}
          className="inline-flex items-center space-x-1 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-secondary)] transition-colors"
        >
          <span>Return to agent list</span>
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
