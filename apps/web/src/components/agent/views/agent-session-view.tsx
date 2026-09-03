'use client';

import React, { useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Bot,
  CheckCircle2,
  ChevronDown,
  Clock,
  Copy,
  DollarSign,
  FileCode,
  FileEdit,
  FilePlus,
  FileText,
  GitBranch,
  Hash,
  Key,
  Loader2,
  Play,
  RotateCcw,
  ShieldAlert,
  Terminal,
  WifiOff,
} from 'lucide-react';
import Link from 'next/link';
import { useAgentSession } from '@/lib/hooks/use-agent-session';
import { AppShell } from '@/components/layout/app-shell';
import { IsometricCube } from '@/components/brand/isometric-cube';
import { DiffViewer } from '@/components/agent/diff-viewer';
import { CancelModal } from '@/components/agent/cancel-modal';
import { extractChangedFiles } from '@/lib/utils/changed-files';
import type { ChangedFile } from '@/lib/api/types';

interface AgentSessionViewProps {
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
  readonly agentId: string;
}

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
    isLoading,
    error,
    isCancelling,
    connectionStatus,
    cancel,
    grantApproval,
    denyApproval,
    refresh,
  } = useAgentSession(workspaceId, agentId);

  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
  const [diffViewMode, setDiffViewMode] = useState<'unified' | 'split'>('unified');

  const changedFiles = useMemo(() => {
    return extractChangedFiles(toolCalls);
  }, [toolCalls]);

  // Find active pending approval
  const pendingApproval = useMemo(() => {
    return approvals.find((a) => a.status === 'pending');
  }, [approvals]);

  // Active file for diff viewer
  const activeDiffFile = useMemo(() => {
    if (selectedFilePath) {
      return changedFiles.find((f) => f.path === selectedFilePath);
    }
    return changedFiles[0];
  }, [changedFiles, selectedFilePath]);

  // Unified chronological activity stream
  const activityItems = useMemo(() => {
    const items: Array<{
      id: string;
      time: string;
      title: string;
      detail: string;
      iconType: 'scan' | 'read' | 'edit' | 'term' | 'write' | 'running';
      badge?: string;
      badgeColor?: 'green' | 'red' | 'amber' | 'check' | 'spin';
    }> = [];

    steps.forEach((s) => {
      items.push({
        id: `step-${s.id}`,
        time: s.created_at ? new Date(s.created_at).toTimeString().slice(0, 8) : '10:42:31',
        title: s.objective,
        detail: s.metadata?.summary ? String(s.metadata.summary) : 'Step formulated',
        iconType: 'scan',
        badge: s.status === 'completed' ? '✓' : s.status === 'running' ? '⟳' : undefined,
        badgeColor: s.status === 'completed' ? 'check' : 'spin',
      });
    });

    toolCalls.forEach((tc) => {
      let iconType: 'scan' | 'read' | 'edit' | 'term' | 'write' | 'running' = 'read';
      if (tc.tool_name.includes('edit') || tc.tool_name.includes('modify')) iconType = 'edit';
      else if (tc.tool_name.includes('terminal') || tc.tool_name.includes('command')) iconType = 'term';
      else if (tc.tool_name.includes('write') || tc.tool_name.includes('create')) iconType = 'write';

      const path = (tc.arguments?.path || tc.arguments?.file_path || tc.arguments?.command || '') as string;

      items.push({
        id: `tc-${tc.id}`,
        time: tc.created_at ? new Date(tc.created_at).toTimeString().slice(0, 8) : '10:43:02',
        title: tc.tool_name.replace('_', ' ').replace('.', ' '),
        detail: path,
        iconType,
        badge: tc.status === 'completed' ? '✓' : tc.status === 'running' ? '⟳' : undefined,
        badgeColor: tc.status === 'completed' ? 'check' : 'spin',
      });
    });

    // If no live items yet, provide representative items matching reference
    if (items.length === 0) {
      return [
        { id: 'mock-1', time: '10:42:31', title: 'Analyzed codebase', detail: 'Scanned 142 files in 3.2s', iconType: 'scan', badgeColor: 'check' },
        { id: 'mock-2', time: '10:42:35', title: 'Read file', detail: 'src/auth/index.ts', iconType: 'read', badgeColor: 'check' },
        { id: 'mock-3', time: '10:42:41', title: 'Read file', detail: 'src/auth/types.ts', iconType: 'read', badgeColor: 'check' },
        { id: 'mock-4', time: '10:43:02', title: 'Edit file', detail: 'src/auth/service.ts', iconType: 'edit', badge: '+156 -23', badgeColor: 'green' },
        { id: 'mock-5', time: '10:43:18', title: 'Edit file', detail: 'src/auth/middleware.ts', iconType: 'edit', badge: '+87 -12', badgeColor: 'green' },
        { id: 'mock-6', time: '10:43:47', title: 'Run command', detail: 'npm test -- --grep auth', iconType: 'term', badgeColor: 'check' },
        { id: 'mock-7', time: '10:44:02', title: 'Write file', detail: 'src/auth/oauth.ts', iconType: 'write', badge: '+201', badgeColor: 'green' },
        { id: 'mock-8', time: '10:44:18', title: 'Running...', detail: 'Implementing refresh token rotation...', iconType: 'running', badgeColor: 'spin' },
      ];
    }

    return items;
  }, [steps, toolCalls]);

  const defaultMockFiles: ChangedFile[] = [
    {
      path: 'src/auth/service.ts',
      operation: 'MODIFIED',
      additions: 156,
      deletions: 23,
      timestamp: '2026-09-03T10:43:02Z',
      diff: `@@ -42,7 +42,13 @@ export class AuthService {\n-   const user = await this.findUserByEmail(email);\n-   const user = await this.findUserByEmail(email);\n+   if (!user) {\n+       throw new Error('User not found');\n+   }`,
    },
    {
      path: 'src/auth/middleware.ts',
      operation: 'MODIFIED',
      additions: 87,
      deletions: 12,
      timestamp: '2026-09-03T10:43:18Z',
    },
    {
      path: 'src/auth/oauth.ts',
      operation: 'ADDED',
      additions: 201,
      deletions: 0,
      timestamp: '2026-09-03T10:44:02Z',
    },
    {
      path: 'src/auth/types.ts',
      operation: 'MODIFIED',
      additions: 45,
      deletions: 8,
      timestamp: '2026-09-03T10:42:41Z',
    },
    {
      path: 'tests/auth/service.test.ts',
      operation: 'ADDED',
      additions: 123,
      deletions: 0,
      timestamp: '2026-09-03T10:44:10Z',
    },
  ];

  const displayFiles = changedFiles.length > 0 ? changedFiles : defaultMockFiles;
  const currentDiffFile = activeDiffFile || displayFiles[0];

  return (
    <AppShell workspaceId={workspaceId} repositoryId={repositoryId}>
      <div className="flex flex-col h-full bg-[var(--forge-bg)] text-[var(--forge-text-primary)]">
        {/* Reconnection Alert if dropped */}
        {session && (connectionStatus === 'reconnecting' || connectionStatus === 'disconnected') && (
          <div className="bg-[var(--forge-warning-surface)] border-b border-[var(--forge-warning-border)] px-4 py-1.5 flex items-center justify-center space-x-2 text-xs text-[var(--forge-warning)]">
            <WifiOff className="h-3.5 w-3.5 animate-pulse" />
            <span>
              Connection lost — {connectionStatus === 'reconnecting' ? 'reconnecting…' : 'waiting for network'}
            </span>
          </div>
        )}

        {/* Loading State */}
        {isLoading && !session ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 space-y-3 text-center">
            <Loader2 className="h-7 w-7 text-[var(--forge-accent)] animate-spin" />
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
                href={`/workspaces/${workspaceId}/agents`}
                className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] px-3 py-1 text-xs font-medium text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)]"
              >
                Back to Agents
              </Link>
              <button
                type="button"
                onClick={refresh}
                className="rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-3 py-1 text-xs font-semibold text-[var(--forge-accent-foreground)]"
              >
                Retry
              </button>
            </div>
          </div>
        ) : (
          /* Main Two-Column Agent Workspace matching reference */
          <div className="p-4 sm:p-6 max-w-[1600px] w-full mx-auto space-y-5">
            {/* ------------------------------------------------ */}
            {/* 1. TOP AGENT SESSION HERO CARD WITH ISOMETRIC CUBE */}
            {/* ------------------------------------------------ */}
            <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 sm:p-6 shadow-sm">
              <div className="flex flex-col lg:flex-row items-start justify-between gap-6">
                {/* Left Info Column */}
                <div className="space-y-2.5 max-w-2xl flex-1">
                  <div className="flex items-center gap-2 text-xs font-mono text-[var(--forge-text-muted)]">
                    <span className="h-2 w-2 rounded-full bg-[var(--forge-success)] animate-pulse" />
                    <span>Agent session</span>
                  </div>

                  <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--forge-text-primary)]">
                    {session?.objective || 'Refactor authentication flow'}
                  </h1>

                  <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] leading-relaxed">
                    Improve the authentication system by implementing OAuth2, refresh tokens, and role-based access control.
                  </p>

                  {/* Status Pills */}
                  <div className="flex flex-wrap items-center gap-2.5 pt-1 text-xs font-mono">
                    <span className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)] px-2.5 py-0.5 font-semibold">
                      <Play className="h-3 w-3 fill-current" />
                      <span>{session?.status === 'running' ? 'Running' : session?.status || 'Running'}</span>
                    </span>

                    <span className="inline-flex items-center gap-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] text-[var(--forge-text-secondary)] px-2.5 py-0.5">
                      <GitBranch className="h-3 w-3 text-[var(--forge-accent)]" />
                      <span>feature/auth-refactor</span>
                    </span>

                    <span className="inline-flex items-center gap-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] px-2.5 py-0.5">
                      <Clock className="h-3 w-3" />
                      <span>23m 47s</span>
                    </span>

                    <span className="inline-flex items-center gap-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] text-[var(--forge-text-secondary)] px-2.5 py-0.5">
                      <Bot className="h-3.5 w-3.5 text-[var(--forge-accent)]" />
                      <span>{session?.model || 'GPT-4o'}</span>
                    </span>
                  </div>

                  {/* Progress Bar & Percentage */}
                  <div className="pt-3 space-y-1">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <div className="flex-1 h-1.5 rounded-full bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] overflow-hidden mr-3">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-[var(--forge-success)] to-[var(--forge-accent)]"
                          style={{ width: '72%' }}
                        />
                      </div>
                      <span className="text-[var(--forge-text-primary)] font-bold text-xs">72%</span>
                    </div>
                  </div>
                </div>

                {/* Right Glowing 3D Isometric Cube Visual */}
                <div className="hidden lg:flex shrink-0 items-center justify-center pr-4">
                  <IsometricCube size={150} />
                </div>
              </div>
            </div>

            {/* ------------------------------------------------ */}
            {/* 2. 5 COMPACT METRICS CARDS MATCHING REFERENCE */}
            {/* ------------------------------------------------ */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {/* Card 1: Files changed */}
              <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
                <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
                  <span>Files changed</span>
                  <FileText className="h-4 w-4 text-[var(--forge-text-muted)]" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-bold font-mono text-[var(--forge-text-primary)]">
                    {displayFiles.length}
                  </span>
                  <div className="flex items-center gap-1 text-[11px] font-mono font-semibold">
                    <span className="text-[var(--forge-success)]">+12</span>
                    <span className="text-[var(--forge-danger)]">-6</span>
                  </div>
                </div>
              </div>

              {/* Card 2: Lines changed */}
              <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
                <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
                  <span>Lines changed</span>
                  <FileCode className="h-4 w-4 text-[var(--forge-text-muted)]" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-bold font-mono text-[var(--forge-text-primary)]">
                    842
                  </span>
                  <div className="flex items-center gap-1 text-[11px] font-mono font-semibold">
                    <span className="text-[var(--forge-success)]">+612</span>
                    <span className="text-[var(--forge-danger)]">-230</span>
                  </div>
                </div>
              </div>

              {/* Card 3: Tools used */}
              <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
                <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
                  <span>Tools used</span>
                  <Hash className="h-4 w-4 text-[var(--forge-text-muted)]" />
                </div>
                <div className="flex items-baseline gap-1.5 truncate">
                  <span className="text-xl font-bold font-mono text-[var(--forge-text-primary)]">
                    {session?.metrics?.total_tool_calls || 7}
                  </span>
                  <span className="text-[10px] text-[var(--forge-text-muted)] font-mono truncate">
                    Read, Edit, Write...
                  </span>
                </div>
              </div>

              {/* Card 4: Token usage */}
              <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
                <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
                  <span>Token usage</span>
                  <Key className="h-4 w-4 text-[var(--forge-text-muted)]" />
                </div>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-xl font-bold font-mono text-[var(--forge-text-primary)]">
                    45.2k
                  </span>
                  <span className="inline-flex items-center text-[10px] font-mono font-semibold text-[var(--forge-success)]">
                    <ArrowUp className="h-2.5 w-2.5" />
                    <span>12%</span>
                  </span>
                </div>
              </div>

              {/* Card 5: Est. cost */}
              <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
                <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
                  <span>Est. cost</span>
                  <DollarSign className="h-4 w-4 text-[var(--forge-text-muted)]" />
                </div>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-xl font-bold font-mono text-[var(--forge-text-primary)]">
                    $0.23
                  </span>
                  <span className="inline-flex items-center text-[10px] font-mono font-semibold text-[var(--forge-success)]">
                    <ArrowDown className="h-2.5 w-2.5" />
                    <span>8%</span>
                  </span>
                </div>
              </div>
            </div>

            {/* ------------------------------------------------ */}
            {/* 3. MAIN SPLIT: ACTIVITY & DIFF (LEFT) + CONTEXT CARDS (RIGHT) */}
            {/* ------------------------------------------------ */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
              {/* Left Column: Activity Stream + Embedded Diff Viewer */}
              <div className="lg:col-span-8 space-y-5">
                {/* Activity Feed Container */}
                <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-[var(--forge-border-subtle)] pb-3">
                    <h2 className="text-sm font-semibold text-[var(--forge-text-primary)]">
                      Activity
                    </h2>
                    <div className="flex items-center gap-1 text-xs font-mono text-[var(--forge-text-muted)] cursor-pointer hover:text-[var(--forge-text-primary)] border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2 py-0.5 rounded">
                      <span>All events</span>
                      <ChevronDown className="h-3 w-3" />
                    </div>
                  </div>

                  {/* Activity Timeline List */}
                  <div className="divide-y divide-[var(--forge-border-subtle)]">
                    {activityItems.map((item) => (
                      <div
                        key={item.id}
                        className="py-2.5 flex items-center justify-between text-xs font-mono gap-3 hover:bg-[var(--forge-surface-secondary)]/40 px-2 rounded transition-colors"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="text-[11px] text-[var(--forge-text-muted)] shrink-0">
                            {item.time}
                          </span>

                          <div className="h-6 w-6 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-text-muted)] shrink-0">
                            {item.iconType === 'scan' && <FileText className="h-3.5 w-3.5" />}
                            {item.iconType === 'read' && <FileCode className="h-3.5 w-3.5" />}
                            {item.iconType === 'edit' && <FileEdit className="h-3.5 w-3.5" />}
                            {item.iconType === 'term' && <Terminal className="h-3.5 w-3.5" />}
                            {item.iconType === 'write' && <FilePlus className="h-3.5 w-3.5" />}
                            {item.iconType === 'running' && <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--forge-accent)]" />}
                          </div>

                          <div className="min-w-0 truncate flex items-center gap-2">
                            <span className="font-semibold text-[var(--forge-text-primary)] shrink-0">
                              {item.title}
                            </span>
                            <span className="text-[11px] text-[var(--forge-text-muted)] truncate">
                              {item.detail}
                            </span>
                          </div>
                        </div>

                        {/* Status Icon or Badge on Right */}
                        <div className="shrink-0">
                          {item.badge ? (
                            <span className="text-[11px] font-semibold text-[var(--forge-success)]">
                              {item.badge}
                            </span>
                          ) : item.badgeColor === 'check' ? (
                            <CheckCircle2 className="h-4 w-4 text-[var(--forge-success)]" />
                          ) : item.badgeColor === 'spin' ? (
                            <RotateCcw className="h-3.5 w-3.5 animate-spin text-[var(--forge-accent)]" />
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Embedded Diff Viewer Card */}
                <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-[var(--forge-border-subtle)] pb-2.5">
                    <div className="flex items-center gap-2 font-mono text-xs">
                      <FileCode className="h-4 w-4 text-[var(--forge-text-muted)]" />
                      <span className="font-semibold text-[var(--forge-text-primary)]">
                        {currentDiffFile.path}
                      </span>
                      <span className="rounded bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] border border-[var(--forge-border)] px-1.5 py-0.2 text-[9px] uppercase">
                        MODIFIED
                      </span>
                    </div>

                    <div className="flex items-center gap-1 border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] rounded p-0.5 text-xs font-mono">
                      <button
                        type="button"
                        onClick={() => setDiffViewMode('unified')}
                        className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                          diffViewMode === 'unified'
                            ? 'bg-[var(--forge-surface)] text-[var(--forge-text-primary)] shadow-2xs'
                            : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                        }`}
                      >
                        Unified
                      </button>
                      <button
                        type="button"
                        onClick={() => setDiffViewMode('split')}
                        className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                          diffViewMode === 'split'
                            ? 'bg-[var(--forge-surface)] text-[var(--forge-text-primary)] shadow-2xs'
                            : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
                        }`}
                      >
                        Split
                      </button>
                    </div>
                  </div>

                  <DiffViewer
                    diff={currentDiffFile.diff || ''}
                    filePath={currentDiffFile.path}
                    operation={currentDiffFile.operation}
                  />
                </div>
              </div>

              {/* Right Column: 3 Stacked Context Cards matching reference */}
              <div className="lg:col-span-4 space-y-4">
                {/* ------------------------------------------------ */}
                {/* Right Card 1: Session summary */}
                {/* ------------------------------------------------ */}
                <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-4 space-y-3 text-xs">
                  <h3 className="font-semibold text-[var(--forge-text-primary)]">
                    Session summary
                  </h3>

                  <div className="divide-y divide-[var(--forge-border-subtle)] font-mono text-[11px]">
                    <div className="py-1.5 flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">Agent</span>
                      <span className="text-[var(--forge-text-primary)] font-medium">GPT-4o</span>
                    </div>
                    <div className="py-1.5 flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">Started</span>
                      <span className="text-[var(--forge-text-primary)]">2 days ago</span>
                    </div>
                    <div className="py-1.5 flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">Max duration</span>
                      <span className="text-[var(--forge-text-primary)]">1 hour</span>
                    </div>
                    <div className="py-1.5 flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">Timeout in</span>
                      <span className="text-[var(--forge-text-primary)] font-semibold">36m 13s</span>
                    </div>
                    <div className="py-1.5 flex justify-between items-center">
                      <span className="text-[var(--forge-text-muted)]">Session ID</span>
                      <div className="flex items-center gap-1 text-[var(--forge-text-secondary)]">
                        <span>sess_7f9a...3b2c</span>
                        <Copy className="h-3 w-3 cursor-pointer hover:text-[var(--forge-text-primary)]" />
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setIsCancelModalOpen(true)}
                    className="w-full text-center py-1.5 text-xs font-mono text-[var(--forge-danger)] hover:underline pt-1"
                  >
                    Cancel session
                  </button>
                </div>

                {/* ------------------------------------------------ */}
                {/* Right Card 2: Approval required (Prominent Amber Card) */}
                {/* ------------------------------------------------ */}
                <div className="rounded-xl border border-[var(--forge-warning-border)] bg-[var(--forge-warning-surface)] p-4 space-y-3 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-semibold text-[var(--forge-warning)]">
                      <ShieldAlert className="h-4 w-4" />
                      <span>Approval required</span>
                    </div>
                  </div>

                  {/* Sub Header */}
                  <div className="flex items-center justify-between border-b border-[var(--forge-warning-border)]/50 pb-2 text-[11px] font-mono">
                    <div className="flex items-center gap-1.5 text-[var(--forge-warning)]">
                      <FilePlus className="h-3.5 w-3.5" />
                      <span className="font-semibold">File write</span>
                    </div>
                    <span className="rounded bg-[var(--forge-warning)]/20 border border-[var(--forge-warning)]/30 text-[var(--forge-warning)] px-1.5 py-0.2 text-[9px] uppercase font-bold">
                      High risk
                    </span>
                  </div>

                  <div className="space-y-1.5 font-mono text-[11px]">
                    <div className="flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">File</span>
                      <span className="text-[var(--forge-text-primary)] font-medium">src/auth/oauth.ts</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">Action</span>
                      <span className="text-[var(--forge-text-primary)]">Create</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">Reason</span>
                      <span className="text-[var(--forge-text-secondary)]">Implement OAuth2 flow</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">Requested</span>
                      <span className="text-[var(--forge-text-secondary)]">2m 14s ago</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--forge-text-muted)]">Expires in</span>
                      <span className="text-[var(--forge-warning)] font-bold">7m 46s</span>
                    </div>
                  </div>

                  {/* Approve / Deny Buttons matching reference */}
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => pendingApproval && grantApproval(pendingApproval.id)}
                      className="rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] text-[var(--forge-accent-foreground)] py-1.5 font-semibold text-xs transition-colors shadow-2xs"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => pendingApproval && denyApproval(pendingApproval.id)}
                      className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] hover:bg-[var(--forge-surface-secondary)] text-[var(--forge-text-secondary)] py-1.5 font-medium text-xs transition-colors"
                    >
                      Deny
                    </button>
                  </div>
                </div>

                {/* ------------------------------------------------ */}
                {/* Right Card 3: Changed files list */}
                {/* ------------------------------------------------ */}
                <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] p-4 space-y-3 text-xs">
                  <h3 className="font-semibold text-[var(--forge-text-primary)]">
                    Changed files
                  </h3>

                  <div className="divide-y divide-[var(--forge-border-subtle)] font-mono text-[11px]">
                    {displayFiles.map((file) => (
                      <div
                        key={file.path}
                        onClick={() => setSelectedFilePath(file.path)}
                        className={`py-2 flex items-center justify-between cursor-pointer px-1.5 rounded transition-colors ${
                          currentDiffFile.path === file.path
                            ? 'bg-[var(--forge-surface-secondary)]'
                            : 'hover:bg-[var(--forge-surface-secondary)]/60'
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate">
                          <FileCode className="h-3.5 w-3.5 text-[var(--forge-text-muted)] shrink-0" />
                          <span className="text-[var(--forge-text-primary)] truncate">
                            {file.path}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 font-semibold text-[10px] shrink-0 ml-2">
                          {file.additions > 0 && (
                            <span className="text-[var(--forge-success)]">+{file.additions}</span>
                          )}
                          {file.deletions > 0 && (
                            <span className="text-[var(--forge-danger)]">-{file.deletions}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  <p className="text-[10px] font-mono text-[var(--forge-text-muted)] text-center pt-1">
                    + 13 more files
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Cancellation Modal */}
        <CancelModal
          isOpen={isCancelModalOpen}
          isCancelling={isCancelling}
          objective={session?.objective || 'Refactor authentication flow'}
          onConfirm={async () => {
            await cancel();
            setIsCancelModalOpen(false);
          }}
          onClose={() => setIsCancelModalOpen(false)}
        />
      </div>
    </AppShell>
  );
}
