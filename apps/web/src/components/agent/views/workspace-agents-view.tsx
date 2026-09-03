'use client';

import { useCallback, useEffect, useState } from 'react';
import { agentService } from '@/lib/api/agent';
import type { AgentSession } from '@/lib/api/types';
import { AgentList } from '@/components/agent/agent-list';
import { AppShell } from '@/components/layout/app-shell';

interface WorkspaceAgentsViewProps {
  readonly workspaceId: string;
}

export function WorkspaceAgentsView({ workspaceId }: WorkspaceAgentsViewProps) {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchAgents = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await agentService.listSessions(workspaceId, {}, signal);
        setSessions(res.items);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsLoading(false);
      }
    },
    [workspaceId]
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchAgents(controller.signal);
    return () => controller.abort();
  }, [fetchAgents]);

  const activeCount = sessions.filter((s) => ['created', 'planning', 'running'].includes(s.status)).length;

  return (
    <AppShell workspaceId={workspaceId} activeAgentCount={activeCount}>
      <div className="max-w-6xl w-full mx-auto p-4 sm:p-6 space-y-5">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold tracking-tight text-[var(--forge-text-primary)]">
            Workspace Agents
          </h1>
          <p className="text-xs text-[var(--forge-text-secondary)]">
            Autonomous engineering agents executing tasks across repositories in this workspace.
          </p>
        </div>

        <AgentList
          sessions={sessions}
          workspaceId={workspaceId}
          isLoading={isLoading}
          error={error}
          onRefresh={fetchAgents}
        />
      </div>
    </AppShell>
  );
}
