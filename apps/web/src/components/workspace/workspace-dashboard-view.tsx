'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Bot,
  Brain,
  CheckCircle2,
  FolderGit2,
  Plus,
  ShieldAlert,
} from 'lucide-react';
import { agentService } from '@/lib/api/agent';
import type { AgentSession } from '@/lib/api/types';
import { AgentCard } from '@/components/agent/agent-card';
import { AppShell } from '@/components/layout/app-shell';

interface WorkspaceDashboardViewProps {
  readonly workspaceId: string;
}

export function WorkspaceDashboardView({ workspaceId }: WorkspaceDashboardViewProps) {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    agentService
      .listSessions(workspaceId)
      .then((res) => setSessions(res.items))
      .catch(() => setSessions([]))
      .finally(() => setIsLoading(false));
  }, [workspaceId]);

  const activeAgents = sessions.filter((s) =>
    ['created', 'planning', 'running'].includes(s.status)
  );
  const pendingApprovals = sessions.filter(
    (s) => s.status === 'waiting_for_approval'
  );
  const completedAgents = sessions.filter((s) => s.status === 'completed');

  return (
    <AppShell workspaceId={workspaceId} activeAgentCount={activeAgents.length}>
      <div className="max-w-6xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-0.5">
            <h1 className="text-xl font-semibold tracking-tight text-[var(--forge-text-primary)]">
              Workspace Overview
            </h1>
            <p className="text-xs text-[var(--forge-text-secondary)] font-mono">
              Workspace ID: {workspaceId}
            </p>
          </div>

          <Link
            href={`/workspaces/${workspaceId}/agents/new`}
            className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-3.5 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors self-start sm:self-auto"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Launch Agent</span>
          </Link>
        </div>

        {/* Priority Status Tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
            <div className="flex items-center justify-between text-xs text-[var(--forge-text-secondary)]">
              <span className="font-medium">Active Agents</span>
              <Bot className="h-4 w-4 text-[var(--forge-text-muted)]" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-[var(--forge-text-primary)]">
                {activeAgents.length}
              </span>
              {activeAgents.length > 0 && (
                <span className="text-[10px] text-[var(--forge-success)] font-mono animate-pulse">
                  executing
                </span>
              )}
            </div>
          </div>

          <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
            <div className="flex items-center justify-between text-xs text-[var(--forge-text-secondary)]">
              <span className="font-medium">Pending Approvals</span>
              <ShieldAlert className="h-4 w-4 text-[var(--forge-warning)]" />
            </div>
            <div className="flex items-baseline gap-2">
              <span
                className={`text-xl font-bold font-mono ${
                  pendingApprovals.length > 0
                    ? 'text-[var(--forge-warning)]'
                    : 'text-[var(--forge-text-primary)]'
                }`}
              >
                {pendingApprovals.length}
              </span>
              {pendingApprovals.length > 0 && (
                <span className="text-[10px] text-[var(--forge-warning)] font-mono">
                  action required
                </span>
              )}
            </div>
          </div>

          <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
            <div className="flex items-center justify-between text-xs text-[var(--forge-text-secondary)]">
              <span className="font-medium">Completed Tasks</span>
              <CheckCircle2 className="h-4 w-4 text-[var(--forge-success)]" />
            </div>
            <span className="text-xl font-bold font-mono text-[var(--forge-text-primary)]">
              {completedAgents.length}
            </span>
          </div>

          <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-1">
            <div className="flex items-center justify-between text-xs text-[var(--forge-text-secondary)]">
              <span className="font-medium">Context & Memory</span>
              <Brain className="h-4 w-4 text-[var(--forge-text-muted)]" />
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-xs font-semibold text-[var(--forge-success)]">
                Synchronized
              </span>
              <span className="text-[10px] text-[var(--forge-text-muted)] font-mono">
                (pgvector)
              </span>
            </div>
          </div>
        </div>

        {/* Pending Approvals Callout */}
        {pendingApprovals.length > 0 && (
          <div className="rounded border border-[var(--forge-warning-border)] bg-[var(--forge-warning-surface)] p-4 space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-semibold text-[var(--forge-warning)]">
              <ShieldAlert className="h-4 w-4" />
              <span>Human Approval Required on {pendingApprovals.length} Agent Session(s)</span>
            </div>
            <p className="text-xs text-[var(--forge-text-secondary)]">
              High-risk operations (such as file modifications or terminal commands) are suspended awaiting authorization.
            </p>
            <div className="space-y-2">
              {pendingApprovals.map((session) => (
                <AgentCard
                  key={session.id}
                  session={session}
                  workspaceId={workspaceId}
                />
              ))}
            </div>
          </div>
        )}

        {/* Active & Recent Agents */}
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-[var(--forge-border)] pb-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--forge-text-primary)]">
              Recent Agent Activity
            </h2>
            <Link
              href={`/workspaces/${workspaceId}/agents`}
              className="text-xs text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors"
            >
              View all ({sessions.length}) →
            </Link>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-16 rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] animate-pulse"
                />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-8 text-center space-y-2.5">
              <Bot className="h-7 w-7 text-[var(--forge-text-muted)] mx-auto" />
              <p className="text-xs font-medium text-[var(--forge-text-primary)]">No agent sessions in this workspace</p>
              <p className="text-[11px] text-[var(--forge-text-muted)]">
                Launch an autonomous agent to inspect symbols, plan changes, and execute terminal tools.
              </p>
              <Link
                href={`/workspaces/${workspaceId}/agents/new`}
                className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-accent)] px-3 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] mt-2 shadow-xs"
              >
                <Plus className="h-3 w-3" />
                <span>Launch First Agent</span>
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {sessions.slice(0, 5).map((session) => (
                <AgentCard
                  key={session.id}
                  session={session}
                  workspaceId={workspaceId}
                />
              ))}
            </div>
          )}
        </div>

        {/* Connected Repositories preview */}
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between border-b border-[var(--forge-border)] pb-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--forge-text-primary)]">
              Connected Repositories
            </h2>
            <Link
              href={`/workspaces/${workspaceId}/repositories`}
              className="text-xs text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors"
            >
              Manage Repositories →
            </Link>
          </div>

          <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FolderGit2 className="h-5 w-5 text-[var(--forge-text-muted)]" />
              <div>
                <p className="text-xs font-semibold text-[var(--forge-text-primary)] font-mono">
                  forge (local repository)
                </p>
                <p className="text-[11px] text-[var(--forge-text-muted)]">
                  Indexed via Tree-sitter AST • Symbol Dependency Graph Active
                </p>
              </div>
            </div>
            <span className="rounded bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)] px-2 py-0.5 text-[10px] font-mono font-medium">
              Ready
            </span>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
