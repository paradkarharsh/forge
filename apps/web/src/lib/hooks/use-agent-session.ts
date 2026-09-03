'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { agentService } from '../api/agent';
import type {
  AgentApproval,
  AgentEvent,
  AgentSession,
  AgentStatus,
  AgentStep,
  AgentToolCall,
} from '../api/types';
import { isTerminalStatus } from '../api/types';
import { useAgentEvents } from './use-agent-events';

export interface UseAgentSessionResult {
  readonly session: AgentSession | null;
  readonly steps: AgentStep[];
  readonly toolCalls: AgentToolCall[];
  readonly approvals: AgentApproval[];
  readonly events: AgentEvent[];
  readonly isLoading: boolean;
  readonly error: Error | null;
  readonly isCancelling: boolean;
  readonly connectionStatus: string;
  readonly cancel: () => Promise<void>;
  readonly run: () => Promise<void>;
  readonly grantApproval: (approvalId: string, reason?: string) => Promise<void>;
  readonly denyApproval: (approvalId: string, reason?: string) => Promise<void>;
  readonly refresh: () => Promise<void>;
}

export function useAgentSession(
  workspaceId: string,
  agentId: string
): UseAgentSessionResult {
  const [session, setSession] = useState<AgentSession | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [toolCalls, setToolCalls] = useState<AgentToolCall[]>([]);
  const [approvals, setApprovals] = useState<AgentApproval[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  // Track if initial load is finished
  const initialLoadDone = useRef(false);

  const fetchFullState = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setError(null);
        const [sessData, stepsData, toolCallsData, approvalsData] =
          await Promise.all([
            agentService.getSession(workspaceId, agentId, signal),
            agentService.getSteps(workspaceId, agentId, signal),
            agentService.getToolCalls(workspaceId, agentId, {}, signal),
            agentService.getApprovals(workspaceId, agentId, signal),
          ]);

        setSession(sessData);
        setSteps(stepsData || []);
        setToolCalls(toolCallsData || []);
        setApprovals(approvalsData || []);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsLoading(false);
        initialLoadDone.current = true;
      }
    },
    [workspaceId, agentId]
  );

  // Initial load
  useEffect(() => {
    const controller = new AbortController();
    fetchFullState(controller.signal);
    return () => {
      controller.abort();
    };
  }, [fetchFullState]);

  // Handle SSE events
  const handleSseEvent = useCallback(
    (event: AgentEvent) => {
      const type = event.event_type;

      // When status changes
      if (
        type === 'session.status' ||
        type === 'agent.planning_started' ||
        type === 'agent.running' ||
        type === 'agent.resumed' ||
        type === 'agent.completed' ||
        type === 'agent.failed' ||
        type === 'agent.cancelled' ||
        type === 'agent.timed_out' ||
        type === 'agent.approval_requested' ||
        type === 'agent.approval_expired'
      ) {
        setSession((prev) => {
          if (!prev) return prev;
          let newStatus = prev.status;
          if (type === 'agent.planning_started') newStatus = 'planning';
          else if (type === 'agent.running' || type === 'agent.resumed') newStatus = 'running';
          else if (type === 'agent.completed') newStatus = 'completed';
          else if (type === 'agent.failed') newStatus = 'failed';
          else if (type === 'agent.cancelled') newStatus = 'cancelled';
          else if (type === 'agent.timed_out') newStatus = 'timed_out';
          else if (type === 'agent.approval_requested') newStatus = 'waiting_for_approval';
          else if (type === 'agent.approval_expired') newStatus = 'expired';
          else if (type === 'session.status' && event.data?.status) {
            newStatus = event.data.status as AgentStatus;
          }
          return { ...prev, status: newStatus };
        });
      }

      // When steps change
      if (
        type === 'agent.step_started' ||
        type === 'agent.step_completed' ||
        type === 'agent.step_failed' ||
        type === 'agent.plan_created'
      ) {
        agentService
          .getSteps(workspaceId, agentId)
          .then((newSteps) => setSteps(newSteps))
          .catch(() => {});
      }

      // When tool calls change
      if (
        type === 'agent.tool_started' ||
        type === 'agent.tool_completed' ||
        type === 'agent.tool_failed'
      ) {
        agentService
          .getToolCalls(workspaceId, agentId)
          .then((newToolCalls) => setToolCalls(newToolCalls))
          .catch(() => {});
      }

      // When approvals change
      if (
        type === 'agent.approval_requested' ||
        type === 'agent.approval_granted' ||
        type === 'agent.approval_denied'
      ) {
        agentService
          .getApprovals(workspaceId, agentId)
          .then((newApprovals) => setApprovals(newApprovals))
          .catch(() => {});
      }
    },
    [workspaceId, agentId]
  );

  const shouldStream = Boolean(
    session && !isTerminalStatus(session.status)
  );

  const {
    events,
    connectionStatus,
    error: sseError,
  } = useAgentEvents(workspaceId, agentId, {
    enabled: shouldStream,
    onEvent: handleSseEvent,
  });

  const cancel = async () => {
    if (isCancelling || !session) return;
    try {
      setIsCancelling(true);
      const updated = await agentService.cancelSession(workspaceId, agentId);
      setSession(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
      throw err;
    } finally {
      setIsCancelling(false);
    }
  };

  const run = async () => {
    if (!session) return;
    try {
      const updated = await agentService.runSession(workspaceId, agentId);
      setSession(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
      throw err;
    }
  };

  const grantApproval = async (approvalId: string, reason?: string) => {
    try {
      const updatedApproval = await agentService.grantApproval(
        workspaceId,
        agentId,
        approvalId,
        { reason }
      );
      setApprovals((prev) =>
        prev.map((a) => (a.id === approvalId ? updatedApproval : a))
      );
      await fetchFullState();
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
      throw err;
    }
  };

  const denyApproval = async (approvalId: string, reason?: string) => {
    try {
      const updatedApproval = await agentService.denyApproval(
        workspaceId,
        agentId,
        approvalId,
        { reason }
      );
      setApprovals((prev) =>
        prev.map((a) => (a.id === approvalId ? updatedApproval : a))
      );
      await fetchFullState();
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)));
      throw err;
    }
  };

  const refresh = async () => {
    await fetchFullState();
  };

  return {
    session,
    steps,
    toolCalls,
    approvals,
    events,
    isLoading,
    error: error || sseError,
    isCancelling,
    connectionStatus,
    cancel,
    run,
    grantApproval,
    denyApproval,
    refresh,
  };
}
