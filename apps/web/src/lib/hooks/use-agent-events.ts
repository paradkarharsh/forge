'use client';

import { useEffect, useRef, useState } from 'react';
import { AgentSseClient, type SseConnectionStatus } from '../api/sse';
import type { AgentEvent } from '../api/types';

export interface UseAgentEventsOptions {
  readonly enabled?: boolean;
  readonly onEvent?: (event: AgentEvent) => void;
}

export interface UseAgentEventsResult {
  readonly events: AgentEvent[];
  readonly connectionStatus: SseConnectionStatus;
  readonly error: Error | null;
  readonly reconnect: () => void;
  readonly disconnect: () => void;
}

export function useAgentEvents(
  workspaceId: string,
  agentId: string,
  options: UseAgentEventsOptions = {}
): UseAgentEventsResult {
  const { enabled = true, onEvent } = options;

  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connectionStatus, setConnectionStatus] =
    useState<SseConnectionStatus>('disconnected');
  const [error, setError] = useState<Error | null>(null);

  const clientRef = useRef<AgentSseClient | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled || !workspaceId || !agentId) {
      return;
    }

    const client = new AgentSseClient({
      workspaceId,
      agentId,
      onEvent: (event) => {
        setEvents((prev) => {
          // Double check deduplication in React state
          if (prev.some((e) => e.id === event.id)) {
            return prev;
          }
          return [...prev, event];
        });
        onEventRef.current?.(event);
      },
      onStatusChange: (status) => {
        setConnectionStatus(status);
      },
      onError: (err) => {
        setError(err);
      },
    });

    clientRef.current = client;
    client.connect();

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [workspaceId, agentId, enabled]);

  const reconnect = () => {
    if (clientRef.current) {
      clientRef.current.connect();
    }
  };

  const disconnect = () => {
    if (clientRef.current) {
      clientRef.current.disconnect();
    }
  };

  return {
    events,
    connectionStatus,
    error,
    reconnect,
    disconnect,
  };
}
