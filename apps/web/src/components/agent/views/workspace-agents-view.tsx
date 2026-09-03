'use client';

import { useCallback, useEffect, useState } from 'react';
import { agentService } from '@/lib/api/agent';
import type { AgentSession } from '@/lib/api/types';
import { AgentList } from '@/components/agent/agent-list';
import { WorkspaceNav } from '@/components/layout/workspace-nav';

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

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      <WorkspaceNav workspaceId={workspaceId} />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Workspace Agents
          </h1>
          <p className="text-xs text-zinc-400">
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
      </main>
    </div>
  );
}
