import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ApiClient, ApiClientError } from '../lib/api/client';
import { AgentService } from '../lib/api/agent';
import type { AgentSession } from '../lib/api/types';

describe('ApiClient', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('unwraps successful Forge envelope { data, error: null }', async () => {
    const mockData = { id: 'sess-123', status: 'created' };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ data: mockData, error: null }),
    } as unknown as Response);

    const client = new ApiClient('http://localhost:8000');
    const result = await client.get('/v1/test');

    expect(result).toEqual(mockData);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/test',
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
      })
    );
  });

  it('maps structured error envelope to ApiClientError', async () => {
    const errorResponse = {
      data: null,
      error: {
        code: 'unauthorized',
        message: 'Invalid access credentials',
        details: { reason: 'token_expired' },
        request_id: 'req-999',
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => errorResponse,
    } as unknown as Response);

    const client = new ApiClient('http://localhost:8000');

    await expect(client.get('/v1/protected')).rejects.toThrow(ApiClientError);

    try {
      await client.get('/v1/protected');
    } catch (err) {
      const apiErr = err as ApiClientError;
      expect(apiErr.code).toBe('unauthorized');
      expect(apiErr.status).toBe(401);
      expect(apiErr.message).toBe('Invalid access credentials');
      expect(apiErr.requestId).toBe('req-999');
    }
  });

  it('handles query parameters correctly', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ data: [], error: null }),
    } as unknown as Response);

    const client = new ApiClient('http://localhost:8000');
    await client.get('/v1/items', { filter: 'active', page: 2, empty: undefined });

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/items?filter=active&page=2',
      expect.anything()
    );
  });
});

describe('AgentService', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('calls POST /v1/workspaces/{wid}/agents when creating a session', async () => {
    const mockSession: Partial<AgentSession> = {
      id: 'sess-abc',
      workspace_id: 'ws-123',
      objective: 'Refactor auth',
      status: 'created',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ data: mockSession, error: null }),
    } as unknown as Response);

    const service = new AgentService();
    const result = await service.createSession('ws-123', {
      objective: 'Refactor auth',
      model: 'gpt-4o',
    });

    expect(result.id).toBe('sess-abc');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/v1/workspaces/ws-123/agents'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ objective: 'Refactor auth', model: 'gpt-4o' }),
      })
    );
  });

  it('calls POST /v1/workspaces/{wid}/agents/{aid}/cancel on cancellation', async () => {
    const cancelledSession: Partial<AgentSession> = {
      id: 'sess-abc',
      status: 'cancelled',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ data: cancelledSession, error: null }),
    } as unknown as Response);

    const service = new AgentService();
    const result = await service.cancelSession('ws-123', 'sess-abc');

    expect(result.status).toBe('cancelled');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/v1/workspaces/ws-123/agents/sess-abc/cancel'),
      expect.objectContaining({ method: 'POST' })
    );
  });
});
