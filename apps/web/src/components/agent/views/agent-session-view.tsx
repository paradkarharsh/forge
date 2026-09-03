'use client';

import React, { useMemo, useState } from 'react';
import { AlertCircle, ArrowLeft, Loader2, ListTodo, FileCode, GitCompare, WifiOff } from 'lucide-react';
import Link from 'next/link';
import { useAgentSession } from '@/lib/hooks/use-agent-session';
import { ActivityFeed } from '@/components/agent/activity-feed';
import { SessionHeader } from '@/components/agent/session-header';
import { SessionSidebar } from '@/components/agent/session-sidebar';
import { AppShell } from '@/components/layout/app-shell';
import { ApprovalPanel } from '@/components/agent/approval-panel';
import { CompletionBanner } from '@/components/agent/completion-banner';
import { FailureBanner } from '@/components/agent/failure-banner';
import { ChangedFilesList } from '@/components/agent/changed-files-list';
import { DiffViewer } from '@/components/agent/diff-viewer';
import { extractChangedFiles } from '@/lib/utils/changed-files';
import type { ChangedFile } from '@/lib/api/types';

interface AgentSessionViewProps {
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
  readonly agentId: string;
}

type TabType = 'activity' | 'files' | 'diff';

export function AgentSessionView({
  workspaceId,
  repositoryId,
  agentId,
}: AgentSessionViewProps) {
  const {
    session,
    steps,
    toolCalls,
    approvals,
    events,
    isLoading,
    error,
    isCancelling,
    connectionStatus,
    cancel,
    grantApproval,
    denyApproval,
    refresh,
  } = useAgentSession(workspaceId, agentId);

  const [activeTab, setActiveTab] = useState<TabType>('activity');
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);

  const changedFiles = useMemo(() => {
    return extractChangedFiles(toolCalls);
  }, [toolCalls]);

  // Find active pending approval
  const pendingApproval = useMemo(() => {
    return approvals.find((a) => a.status === 'pending');
  }, [approvals]);

  const matchingToolCall = useMemo(() => {
    if (!pendingApproval) return null;
    return toolCalls.find((tc) => tc.id === pendingApproval.tool_call_id || tc.approval_id === pendingApproval.id);
  }, [pendingApproval, toolCalls]);

  // Active file for diff viewer
  const activeDiffFile = useMemo(() => {
    if (selectedFilePath) {
      return changedFiles.find((f) => f.path === selectedFilePath);
    }
    return changedFiles[0];
  }, [changedFiles, selectedFilePath]);

  const handleSelectFile = (file: ChangedFile) => {
    setSelectedFilePath(file.path);
    setActiveTab('diff');
  };

  const backHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents`
    : `/workspaces/${workspaceId}/agents`;

  return (
    <AppShell workspaceId={workspaceId} repositoryId={repositoryId}>
      <div className="flex flex-col h-full">
        {/* Reconnection notice */}
        {session && (connectionStatus === 'reconnecting' || connectionStatus === 'disconnected') && (
          <div className="bg-[var(--forge-warning-surface)] border-b border-[var(--forge-warning-border)] px-4 py-1.5 flex items-center justify-center space-x-2 text-xs text-[var(--forge-warning)]">
            <WifiOff className="h-3.5 w-3.5 animate-pulse" />
            <span>
              Connection lost — {connectionStatus === 'reconnecting' ? 'reconnecting…' : 'waiting for network'}
            </span>
          </div>
        )}

        {isLoading && !session ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 space-y-3 text-center">
            <Loader2 className="h-6 w-6 text-[var(--forge-accent)] animate-spin" />
            <div className="space-y-0.5">
              <h3 className="text-xs font-semibold text-[var(--forge-text-primary)]">
                Loading Agent Workspace...
              </h3>
              <p className="text-[11px] text-[var(--forge-text-muted)] font-mono">
                Session ID: {agentId}
              </p>
            </div>
          </div>
        ) : error && !session ? (
          <div className="flex-1 max-w-md mx-auto flex flex-col items-center justify-center p-8 space-y-3 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border border-[var(--forge-danger-border)]">
              <AlertCircle className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-[var(--forge-text-primary)]">
                Unable to load agent session
              </h2>
              <p className="text-xs text-[var(--forge-danger)] font-mono">
                {error.message}
              </p>
            </div>
            <div className="flex items-center gap-2.5 pt-2">
              <Link
                href={backHref}
                className="inline-flex items-center gap-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] px-3 py-1 text-xs font-medium text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:border-[var(--forge-border-highlight)] transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Back to Agents</span>
              </Link>
              <button
                type="button"
                onClick={refresh}
                className="rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-3 py-1 text-xs font-semibold text-[var(--forge-accent-foreground)] transition-colors shadow-xs"
              >
                Retry
              </button>
            </div>
          </div>
        ) : session ? (
          <div className="flex flex-col flex-1 min-h-0">
            <SessionHeader
              workspaceId={workspaceId}
              repositoryId={repositoryId}
              session={session}
              connectionStatus={connectionStatus}
              isCancelling={isCancelling}
              onCancel={cancel}
            />

            <div className="flex-1 p-4 sm:p-5 flex flex-col lg:flex-row gap-5 min-h-0 overflow-hidden">
              {/* Main Center Area: Work Area */}
              <div className="flex-1 min-w-0 flex flex-col overflow-y-auto">
                {/* Prominent Approval Panel if waiting for human decision */}
                {pendingApproval && (
                  <ApprovalPanel
                    approval={pendingApproval}
                    toolCall={matchingToolCall}
                    onApprove={async (appId, reason) => {
                      await grantApproval(appId, reason);
                    }}
                    onDeny={async (appId, reason) => {
                      await denyApproval(appId, reason);
                    }}
                  />
                )}

                {/* Completion Banner */}
                {session.status === 'completed' && (
                  <CompletionBanner
                    session={session}
                    workspaceId={workspaceId}
                    repositoryId={repositoryId}
                    changedFilesCount={changedFiles.length}
                    onReviewChanges={() => setActiveTab('files')}
                    onOpenDiff={() => setActiveTab('diff')}
                  />
                )}

                {/* Failure / Timeout / Expired Banner */}
                {(session.status === 'failed' || session.status === 'timed_out' || session.status === 'expired') && (
                  <FailureBanner
                    session={session}
                    workspaceId={workspaceId}
                    repositoryId={repositoryId}
                    changedFilesCount={changedFiles.length}
                    onReviewChanges={() => setActiveTab('files')}
                  />
                )}

                {/* Navigation Tabs */}
                <div className="flex items-center space-x-1.5 border-b border-[var(--forge-border)] pb-2 mb-3">
                  <button
                    type="button"
                    onClick={() => setActiveTab('activity')}
                    className={`inline-flex items-center space-x-1.5 rounded px-3 py-1 text-xs font-medium transition-colors ${
                      activeTab === 'activity'
                        ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)] shadow-xs'
                        : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                    }`}
                  >
                    <ListTodo className="h-3.5 w-3.5" />
                    <span>Activity Timeline</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('files')}
                    className={`inline-flex items-center space-x-1.5 rounded px-3 py-1 text-xs font-medium transition-colors ${
                      activeTab === 'files'
                        ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)] shadow-xs'
                        : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                    }`}
                  >
                    <FileCode className="h-3.5 w-3.5" />
                    <span>Changed Files</span>
                    {changedFiles.length > 0 && (
                      <span className="rounded-full bg-[var(--forge-surface)] px-1.5 py-0.2 text-[10px] font-mono border border-[var(--forge-border)] text-[var(--forge-text-primary)]">
                        {changedFiles.length}
                      </span>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('diff')}
                    className={`inline-flex items-center space-x-1.5 rounded px-3 py-1 text-xs font-medium transition-colors ${
                      activeTab === 'diff'
                        ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)] shadow-xs'
                        : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                    }`}
                  >
                    <GitCompare className="h-3.5 w-3.5" />
                    <span>Diff Review</span>
                    {changedFiles.length > 0 && (
                      <span className="rounded-full bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)] px-1.5 py-0.2 text-[10px] font-mono">
                        +{changedFiles.reduce((acc, f) => acc + f.additions, 0)}
                      </span>
                    )}
                  </button>
                </div>

                {/* Tab Content */}
                {activeTab === 'activity' && (
                  <div className="flex-1 min-h-[450px] flex flex-col">
                    <ActivityFeed
                      steps={steps}
                      toolCalls={toolCalls}
                      events={events}
                    />
                  </div>
                )}

                {activeTab === 'files' && (
                  <div className="flex-1 min-h-[450px]">
                    <ChangedFilesList
                      files={changedFiles}
                      selectedPath={selectedFilePath || undefined}
                      onSelectFile={handleSelectFile}
                    />
                  </div>
                )}

                {activeTab === 'diff' && (
                  <div className="flex-1 min-h-[450px] space-y-3">
                    {/* File Selector Pills if multiple files changed */}
                    {changedFiles.length > 1 && (
                      <div className="flex flex-wrap gap-1.5 pb-1">
                        {changedFiles.map((file) => (
                          <button
                            key={file.path}
                            type="button"
                            onClick={() => setSelectedFilePath(file.path)}
                            className={`inline-flex items-center space-x-1.5 rounded px-2 py-0.5 text-xs font-mono transition-colors ${
                              (selectedFilePath || changedFiles[0]?.path) === file.path
                                ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)]'
                                : 'bg-[var(--forge-surface)] text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                            }`}
                          >
                            <span>{file.path}</span>
                          </button>
                        ))}
                      </div>
                    )}

                    {activeDiffFile ? (
                      <DiffViewer
                        diff={activeDiffFile.diff || ''}
                        filePath={activeDiffFile.path}
                        operation={activeDiffFile.operation}
                      />
                    ) : (
                      <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-10 text-center">
                        <GitCompare className="mx-auto h-8 w-8 text-[var(--forge-text-muted)] mb-2" />
                        <h4 className="text-xs font-semibold text-[var(--forge-text-primary)]">No diff available</h4>
                        <p className="mt-1 text-xs text-[var(--forge-text-muted)] max-w-sm mx-auto">
                          No file changes have been recorded yet for this session.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Sidebar Details Area */}
              <div className="overflow-y-auto shrink-0">
                <SessionSidebar session={session} approvals={approvals} />
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
