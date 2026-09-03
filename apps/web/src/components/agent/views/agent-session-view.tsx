'use client';

import React, { useMemo, useState } from 'react';
import { AlertCircle, ArrowLeft, Loader2, ListTodo, FileCode, GitCompare, WifiOff } from 'lucide-react';
import Link from 'next/link';
import { useAgentSession } from '@/lib/hooks/use-agent-session';
import { ActivityFeed } from '@/components/agent/activity-feed';
import { SessionHeader } from '@/components/agent/session-header';
import { SessionSidebar } from '@/components/agent/session-sidebar';
import { WorkspaceNav } from '@/components/layout/workspace-nav';
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
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      <WorkspaceNav workspaceId={workspaceId} repositoryId={repositoryId} />

      {/* Reconnection notice */}
      {session && (connectionStatus === 'reconnecting' || connectionStatus === 'disconnected') && (
        <div className="bg-amber-950/40 border-b border-amber-500/30 px-4 py-2 flex items-center justify-center space-x-2 text-xs text-amber-300">
          <WifiOff className="h-3.5 w-3.5 animate-pulse text-amber-400" />
          <span>
            Connection lost — {connectionStatus === 'reconnecting' ? 'reconnecting…' : 'waiting for network'}
          </span>
        </div>
      )}

      {isLoading && !session ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8 space-y-4 text-center">
          <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-200">
              Loading Agent Workspace...
            </h3>
            <p className="text-xs text-zinc-500 font-mono">
              Session ID: {agentId}
            </p>
          </div>
        </div>
      ) : error && !session ? (
        <div className="flex-1 max-w-xl mx-auto flex flex-col items-center justify-center p-8 space-y-4 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="h-6 w-6" />
          </div>
          <div className="space-y-1.5">
            <h2 className="text-base font-semibold text-zinc-100">
              Unable to load agent session
            </h2>
            <p className="text-xs text-rose-300 font-mono">
              {error.message}
            </p>
          </div>
          <div className="flex items-center gap-3 pt-2">
            <Link
              href={backHref}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-3.5 py-1.5 text-xs font-medium text-zinc-300 hover:text-zinc-100 transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to Agents</span>
            </Link>
            <button
              type="button"
              onClick={refresh}
              className="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3.5 py-1.5 text-xs font-medium text-white transition-colors shadow-xs"
            >
              Retry
            </button>
          </div>
        </div>
      ) : session ? (
        <>
          <SessionHeader
            workspaceId={workspaceId}
            repositoryId={repositoryId}
            session={session}
            connectionStatus={connectionStatus}
            isCancelling={isCancelling}
            onCancel={cancel}
          />

          <main className="flex-1 max-w-[1600px] w-full mx-auto p-4 sm:p-6 flex flex-col lg:flex-row gap-6 min-h-0">
            {/* Main Center Area: Work Area */}
            <div className="flex-1 min-w-0 min-h-[500px] lg:min-h-0 flex flex-col">
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
              <div className="flex items-center space-x-2 border-b border-neutral-800 pb-3 mb-4">
                <button
                  type="button"
                  onClick={() => setActiveTab('activity')}
                  className={`inline-flex items-center space-x-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                    activeTab === 'activity'
                      ? 'bg-neutral-800 text-white shadow-xs'
                      : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/60'
                  }`}
                >
                  <ListTodo className="h-3.5 w-3.5" />
                  <span>Activity Timeline</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('files')}
                  className={`inline-flex items-center space-x-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                    activeTab === 'files'
                      ? 'bg-neutral-800 text-white shadow-xs'
                      : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/60'
                  }`}
                >
                  <FileCode className="h-3.5 w-3.5" />
                  <span>Changed Files</span>
                  {changedFiles.length > 0 && (
                    <span className="rounded-full bg-indigo-500/20 px-2 py-0.2 text-[10px] font-bold text-indigo-300">
                      {changedFiles.length}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('diff')}
                  className={`inline-flex items-center space-x-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                    activeTab === 'diff'
                      ? 'bg-neutral-800 text-white shadow-xs'
                      : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/60'
                  }`}
                >
                  <GitCompare className="h-3.5 w-3.5" />
                  <span>Diff Review</span>
                  {changedFiles.length > 0 && (
                    <span className="rounded-full bg-emerald-500/20 px-2 py-0.2 text-[10px] font-bold text-emerald-300">
                      {changedFiles.reduce((acc, f) => acc + f.additions, 0)}
                    </span>
                  )}
                </button>
              </div>

              {/* Tab Content */}
              {activeTab === 'activity' && (
                <div className="flex-1 min-h-0 flex flex-col">
                  <ActivityFeed
                    steps={steps}
                    toolCalls={toolCalls}
                    events={events}
                  />
                </div>
              )}

              {activeTab === 'files' && (
                <div className="flex-1 min-h-0">
                  <ChangedFilesList
                    files={changedFiles}
                    selectedPath={selectedFilePath || undefined}
                    onSelectFile={handleSelectFile}
                  />
                </div>
              )}

              {activeTab === 'diff' && (
                <div className="flex-1 min-h-0 space-y-4">
                  {/* File Selector Pills if multiple files changed */}
                  {changedFiles.length > 1 && (
                    <div className="flex flex-wrap gap-2 pb-2">
                      {changedFiles.map((file) => (
                        <button
                          key={file.path}
                          type="button"
                          onClick={() => setSelectedFilePath(file.path)}
                          className={`inline-flex items-center space-x-1.5 rounded-md px-2.5 py-1 text-xs font-mono transition-colors ${
                            (selectedFilePath || changedFiles[0]?.path) === file.path
                              ? 'bg-neutral-700 text-white'
                              : 'bg-neutral-900 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200'
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
                    <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-12 text-center">
                      <GitCompare className="mx-auto h-10 w-10 text-neutral-600 mb-3" />
                      <h4 className="text-sm font-semibold text-neutral-300">No diff available</h4>
                      <p className="mt-1 text-xs text-neutral-500 max-w-sm mx-auto">
                        No file changes have been recorded yet for this session.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Sidebar Details Area */}
            <SessionSidebar session={session} approvals={approvals} />
          </main>
        </>
      ) : null}
    </div>
  );
}
