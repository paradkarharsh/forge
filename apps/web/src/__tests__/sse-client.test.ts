import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { AgentSseClient } from '../lib/api/sse';
import type { AgentEvent } from '../lib/api/types';

describe('AgentSseClient', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('parses SSE chunks, suppresses duplicates, and notifies subscriber', async () => {
    const receivedEvents: AgentEvent[] = [];

    const streamData = [
      ': ping\n\n',
      'id: evt-001\nevent: agent.planning_started\ndata: {"status":"planning","session_id":"sess-1"}\n\n',
      // Duplicate event id
      'id: evt-001\nevent: agent.planning_started\ndata: {"status":"planning","session_id":"sess-1"}\n\n',
      'id: evt-002\nevent: agent.running\ndata: {"status":"running","session_id":"sess-1"}\n\n',
      'id: evt-003\nevent: agent.completed\ndata: {"status":"completed","session_id":"sess-1"}\n\n',
    ].join('');

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(streamData));
        controller.close();
      },
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
    } as unknown as Response);

    const client = new AgentSseClient({
      workspaceId: 'ws-1',
      agentId: 'sess-1',
      onEvent: (e) => receivedEvents.push(e),
    });

    client.connect();

    // Wait for stream read to finish
    await new Promise((r) => setTimeout(r, 50));

    // Duplicate evt-001 should be suppressed
    expect(receivedEvents).toHaveLength(3);
    expect(receivedEvents[0].id).toBe('evt-001');
    expect(receivedEvents[0].event_type).toBe('agent.planning_started');
    expect(receivedEvents[1].id).toBe('evt-002');
    expect(receivedEvents[1].event_type).toBe('agent.running');
    expect(receivedEvents[2].id).toBe('evt-003');
    expect(receivedEvents[2].event_type).toBe('agent.completed');

    // Terminal status terminates stream
    expect(client.getStatus()).toBe('terminated');

    client.disconnect();
  });

  it('tracks Last-Event-ID across stream', async () => {
    const streamData =
      'id: evt-100\nevent: agent.step_started\ndata: {"step":1}\n\n';

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(streamData));
        controller.close();
      },
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
    } as unknown as Response);

    let receivedId = '';
    const client = new AgentSseClient({
      workspaceId: 'ws-1',
      agentId: 'sess-1',
      onEvent: (e) => {
        receivedId = e.id;
      },
    });

    client.connect();
    await new Promise((r) => setTimeout(r, 50));

    expect(receivedId).toBe('evt-100');
    client.disconnect();
  });
});
