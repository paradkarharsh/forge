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
          className="inline-flex items-center gap-1.5 text-xs text-emerald-400/90 font-mono"
          title="Real-time SSE stream connected"
        >
          <Wifi className="h-3 w-3 text-emerald-400" />
          <span className="hidden sm:inline">Live</span>
        </span>
      );
    }
    if (connectionStatus === 'reconnecting') {
      return (
        <span
          className="inline-flex items-center gap-1.5 text-xs text-amber-400 font-mono animate-pulse"
          title="Stream interrupted, attempting to resume"
        >
          <Radio className="h-3 w-3 text-amber-400" />
          <span>Reconnecting...</span>
        </span>
      );
    }
    if (connectionStatus === 'connecting') {
      return (
        <span className="inline-flex items-center gap-1.5 text-xs text-zinc-400 font-mono">
          <Radio className="h-3 w-3 text-zinc-400" />
          <span>Connecting...</span>
        </span>
      );
    }
    return (
      <span
        className="inline-flex items-center gap-1.5 text-xs text-zinc-500 font-mono"
        title="Event stream disconnected"
      >
        <WifiOff className="h-3 w-3 text-zinc-500" />
      </span>
    );
  };

  const agentListHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents`
    : `/workspaces/${workspaceId}/agents`;

  return (
    <header className="border-b border-zinc-800 bg-zinc-950/70 backdrop-blur-md px-4 sm:px-6 py-4">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs text-zinc-400 mb-2.5">
        <Link
          href={`/workspaces/${workspaceId}`}
          className="hover:text-zinc-200 transition-colors"
        >
          Workspace
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
        {repositoryId && (
          <>
            <span className="inline-flex items-center gap-1 text-zinc-400">
              <GitBranch className="h-3 w-3 text-zinc-500" />
              <span>Repository</span>
            </span>
            <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
          </>
        )}
        <Link
          href={agentListHref}
          className="hover:text-zinc-200 transition-colors"
        >
          Agents
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
        <span className="text-zinc-200 font-mono truncate max-w-[140px] sm:max-w-xs">
          {session.id.slice(0, 8)}
        </span>
      </div>

      {/* Main Title & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1.5 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-lg sm:text-xl font-semibold text-zinc-100 truncate tracking-tight">
              {session.objective}
            </h1>
            <AgentStatusBadge status={session.status} size="md" />
            {renderConnectionStatus()}
          </div>

          <div className="flex items-center gap-4 text-xs text-zinc-400 font-mono">
            <span>
              Elapsed: <strong className="text-zinc-200">{elapsedFormatted}</strong>
            </span>
            {session.model && (
              <span>
                Model: <strong className="text-zinc-300">{session.model}</strong>
              </span>
            )}
            {session.current_step != null && (
              <span>
                Step: <strong className="text-zinc-300">{session.current_step}</strong>
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
              className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 px-3 py-1.5 text-xs font-medium text-rose-300 transition-colors disabled:opacity-50"
            >
              <Ban className="h-3.5 w-3.5" />
              <span>Cancel Agent</span>
            </button>
          )}
        </div>
      </div>

      {/* Reconnect notice banner when reconnecting */}
      {connectionStatus === 'reconnecting' && (
        <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300 flex items-center gap-2">
          <Radio className="h-3.5 w-3.5 animate-pulse" />
          <span>Connection lost — reconnecting... The agent is continuing to execute on the worker.</span>
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
