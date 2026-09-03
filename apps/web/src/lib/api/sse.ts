import { apiClient } from './client';
import type { AgentEvent } from './types';

export type SseConnectionStatus =
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected'
  | 'terminated';

export interface SseClientOptions {
  readonly workspaceId: string;
  readonly agentId: string;
  readonly onEvent: (event: AgentEvent) => void;
  readonly onStatusChange?: (status: SseConnectionStatus) => void;
  readonly onError?: (error: Error) => void;
  readonly maxRetries?: number;
}

const TERMINAL_EVENT_TYPES = new Set([
  'agent.completed',
  'agent.failed',
  'agent.cancelled',
  'agent.timed_out',
  'completed',
  'failed',
  'cancelled',
]);

export class AgentSseClient {
  private readonly workspaceId: string;
  private readonly agentId: string;
  private readonly onEvent: (event: AgentEvent) => void;
  private readonly onStatusChange?: (status: SseConnectionStatus) => void;
  private readonly onError?: (error: Error) => void;
  private readonly maxRetries: number;

  private status: SseConnectionStatus = 'disconnected';
  private abortController: AbortController | null = null;
  private lastEventId: string | null = null;
  private readonly seenEventIds = new Set<string>();
  private retryCount = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isIntentionallyClosed = false;

  constructor(options: SseClientOptions) {
    this.workspaceId = options.workspaceId;
    this.agentId = options.agentId;
    this.onEvent = options.onEvent;
    this.onStatusChange = options.onStatusChange;
    this.onError = options.onError;
    this.maxRetries = options.maxRetries ?? 10;
  }

  getStatus(): SseConnectionStatus {
    return this.status;
  }

  private setStatus(newStatus: SseConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.onStatusChange?.(newStatus);
    }
  }

  connect(): void {
    this.isIntentionallyClosed = false;
    this.retryCount = 0;
    this.startStream();
  }

  disconnect(): void {
    this.isIntentionallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    this.setStatus('disconnected');
  }

  private async startStream(): Promise<void> {
    if (this.isIntentionallyClosed) {
      return;
    }

    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();
    const signal = this.abortController.signal;

    this.setStatus(this.retryCount === 0 ? 'connecting' : 'reconnecting');

    const baseUrl = apiClient.getBaseUrl();
    const query = this.lastEventId ? `?last_event_id=${encodeURIComponent(this.lastEventId)}` : '';
    const url = `${baseUrl}/v1/workspaces/${this.workspaceId}/agents/${this.agentId}/events${query}`;

    try {
      const headers: Record<string, string> = {
        Accept: 'text/event-stream',
      };
      if (this.lastEventId) {
        headers['Last-Event-ID'] = this.lastEventId;
      }

      const response = await fetch(url, {
        headers,
        signal,
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`SSE stream failed with status ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      this.setStatus('connected');
      this.retryCount = 0; // reset backoff on successful connection

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (!signal.aborted) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const block of lines) {
          this.parseBlock(block);
        }
      }

      // If finished cleanly or stream closed by backend
      if (!this.isIntentionallyClosed) {
        this.scheduleReconnect();
      }
    } catch (err: unknown) {
      if (this.isIntentionallyClosed || signal.aborted) {
        return;
      }

      const error = err instanceof Error ? err : new Error(String(err));
      this.onError?.(error);
      this.scheduleReconnect();
    }
  }

  private parseBlock(block: string): void {
    if (!block.trim()) {
      return;
    }

    let id: string | null = null;
    let eventType = 'message';
    const dataLines: string[] = [];

    const lines = block.split('\n');
    for (const line of lines) {
      if (line.startsWith(':')) {
        // Comment / ping heartbeat
        continue;
      }
      if (line.startsWith('id:')) {
        id = line.substring(3).trim();
      } else if (line.startsWith('event:')) {
        eventType = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.substring(5).trim());
      }
    }

    if (id) {
      this.lastEventId = id;
    }

    if (dataLines.length === 0) {
      return;
    }

    const rawData = dataLines.join('\n');
    let parsedData: Record<string, unknown> = {};
    try {
      parsedData = JSON.parse(rawData);
    } catch {
      parsedData = { text: rawData };
    }

    // Duplicate event suppression
    const eventId = id || String(parsedData.id || `${eventType}-${Date.now()}`);
    if (this.seenEventIds.has(eventId)) {
      return;
    }
    this.seenEventIds.add(eventId);

    const event: AgentEvent = {
      id: eventId,
      event_type: eventType,
      session_id: String(parsedData.session_id || this.agentId),
      timestamp: String(parsedData.timestamp || new Date().toISOString()),
      data: parsedData,
    };

    this.onEvent(event);

    // Terminal status received: close SSE cleanly
    if (TERMINAL_EVENT_TYPES.has(eventType)) {
      this.isIntentionallyClosed = true;
      this.setStatus('terminated');
    }
  }

  private scheduleReconnect(): void {
    if (this.isIntentionallyClosed) {
      return;
    }

    if (this.retryCount >= this.maxRetries) {
      this.setStatus('disconnected');
      this.onError?.(new Error(`Exceeded maximum SSE reconnection attempts (${this.maxRetries})`));
      return;
    }

    this.setStatus('reconnecting');
    this.retryCount += 1;

    // Bounded exponential backoff: 1s, 2s, 4s, capped at 10s
    const delay = Math.min(1000 * Math.pow(2, this.retryCount - 1), 10000);
    this.reconnectTimer = setTimeout(() => {
      this.startStream();
    }, delay);
  }
}
