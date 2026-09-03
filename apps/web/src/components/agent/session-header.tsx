'use client';

import {
  Ban,
  ChevronRight,
  GitBranch,
  Radio,
  Wifi,
  WifiOff,
} from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import type { AgentSession } from '../../lib/api/types';
import { isCancellableStatus } from '../../lib/api/types';
import { useElapsedTime } from '../../lib/hooks/use-elapsed-time';
import { AgentStatusBadge } from './agent-status-badge';
import { CancelModal } from './cancel-modal';

interface SessionHeaderProps {
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
  readonly session: AgentSession;
  readonly connectionStatus: string;
  readonly isCancelling: boolean;
  readonly onCancel: () => Promise<void>;
}

export function SessionHeader({
  workspaceId,
  repositoryId,
  session,
  connectionStatus,
  isCancelling,
  onCancel,
}: SessionHeaderProps) {
  const [showCancelModal, setShowCancelModal] = useState(false);

  const isCancellable = isCancellableStatus(session.status);
  const isActive = session.status === 'planning' || session.status === 'running';

  const { formatted: elapsedFormatted } = useElapsedTime(
    session.started_at || session.created_at,
    session.completed_at || session.cancelled_at,
    isActive
  );

  const handleConfirmCancel = async () => {
    try {
      await onCancel();
      setShowCancelModal(false);
    } catch {
      // Handled in parent hook
    }
  };

  const renderConnectionStatus = () => {
    if (connectionStatus === 'connected') {
      return (
        <span
          className="inline-flex items-center gap-1.5 text-xs text-[var(--forge-success)] font-mono"
          title="Real-time SSE stream connected"
        >
          <Wifi className="h-3 w-3" />
          <span className="hidden sm:inline">Live</span>
        </span>
      );
    }
    if (connectionStatus === 'reconnecting') {
      return (
        <span
          className="inline-flex items-center gap-1.5 text-xs text-[var(--forge-warning)] font-mono animate-pulse"
          title="Stream interrupted, attempting to resume"
        >
          <Radio className="h-3 w-3" />
          <span>Reconnecting...</span>
        </span>
      );
    }
    if (connectionStatus === 'connecting') {
      return (
        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--forge-text-muted)] font-mono">
          <Radio className="h-3 w-3" />
          <span>Connecting...</span>
        </span>
      );
    }
    return (
      <span
        className="inline-flex items-center gap-1.5 text-xs text-[var(--forge-text-muted)] font-mono"
        title="Event stream disconnected"
      >
        <WifiOff className="h-3 w-3" />
      </span>
    );
  };

  const agentListHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents`
    : `/workspaces/${workspaceId}/agents`;

  return (
    <header className="border-b border-[var(--forge-border)] bg-[var(--forge-surface)] px-4 sm:px-6 py-3.5">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs text-[var(--forge-text-muted)] mb-2">
        <Link
          href={`/workspaces/${workspaceId}`}
          className="hover:text-[var(--forge-text-primary)] transition-colors"
        >
          Workspace
        </Link>
        <ChevronRight className="h-3 w-3 text-[var(--forge-text-muted)]" />
        {repositoryId && (
          <>
            <span className="inline-flex items-center gap-1 text-[var(--forge-text-secondary)]">
              <GitBranch className="h-3 w-3 text-[var(--forge-text-muted)]" />
              <span>Repository</span>
            </span>
            <ChevronRight className="h-3 w-3 text-[var(--forge-text-muted)]" />
          </>
        )}
        <Link
          href={agentListHref}
          className="hover:text-[var(--forge-text-primary)] transition-colors"
        >
          Agents
        </Link>
        <ChevronRight className="h-3 w-3 text-[var(--forge-text-muted)]" />
        <span className="text-[var(--forge-text-secondary)] font-mono truncate max-w-[140px] sm:max-w-xs">
          {session.id.slice(0, 8)}
        </span>
      </div>

      {/* Main Title & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-base sm:text-lg font-semibold text-[var(--forge-text-primary)] truncate tracking-tight">
              {session.objective}
            </h1>
            <AgentStatusBadge status={session.status} size="sm" />
            {renderConnectionStatus()}
          </div>

          <div className="flex items-center gap-4 text-xs text-[var(--forge-text-secondary)] font-mono">
            <span>
              Elapsed: <strong className="text-[var(--forge-text-primary)]">{elapsedFormatted}</strong>
            </span>
            {session.model && (
              <span>
                Model: <strong className="text-[var(--forge-text-primary)]">{session.model}</strong>
              </span>
            )}
            {session.current_step != null && (
              <span>
                Step: <strong className="text-[var(--forge-text-primary)]">{session.current_step}</strong>
              </span>
            )}
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3 shrink-0">
          {isCancellable && (
            <button
              type="button"
              disabled={isCancelling}
              onClick={() => setShowCancelModal(true)}
              className="inline-flex items-center gap-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] hover:border-[var(--forge-danger-border)] hover:bg-[var(--forge-danger-surface)] hover:text-[var(--forge-danger)] px-2.5 py-1 text-xs font-medium text-[var(--forge-text-secondary)] transition-colors disabled:opacity-50"
            >
              <Ban className="h-3.5 w-3.5" />
              <span>Cancel Agent</span>
            </button>
          )}
        </div>
      </div>

      {/* Reconnect notice banner when reconnecting */}
      {connectionStatus === 'reconnecting' && (
        <div className="mt-2.5 rounded border border-[var(--forge-warning-border)] bg-[var(--forge-warning-surface)] px-3 py-1.5 text-xs text-[var(--forge-warning)] flex items-center gap-2">
          <Radio className="h-3.5 w-3.5 animate-pulse" />
          <span>Connection interrupted — resuming event stream... Execution continues on worker.</span>
        </div>
      )}

      {/* Cancel Confirmation Modal */}
      <CancelModal
        isOpen={showCancelModal}
        isCancelling={isCancelling}
        objective={session.objective}
        onConfirm={handleConfirmCancel}
        onClose={() => setShowCancelModal(false)}
      />
    </header>
  );
}
