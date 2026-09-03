import { describe, it, expect, vi, beforeEach } from 'vitest';
import { agentService } from '../lib/api/agent';
import { apiClient } from '../lib/api/client';
import type { AgentApproval } from '../lib/api/types';

describe('Approval UX & Service Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('calls grantApproval with correct URL and reason payload', async () => {
    const mockApproval: AgentApproval = {
      id: 'app-123',
      session_id: 'sess-456',
      tool_call_id: 'tc-789',
      tool_name: 'file.modify',
      arguments_hash: 'sha256-hash',
      status: 'granted',
      requested_by: 'agent',
      decided_by: 'user-1',
      reason: 'Approved safe modification',
      requested_at: '2026-09-03T12:00:00Z',
      decided_at: '2026-09-03T12:01:00Z',
      expires_at: null,
      metadata: {},
    };

    const postSpy = vi
      .spyOn(apiClient, 'post')
      .mockResolvedValue(mockApproval);

    const result = await agentService.grantApproval(
      'ws-1',
      'sess-456',
      'app-123',
      { reason: 'Approved safe modification' }
    );

    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(postSpy).toHaveBeenCalledWith(
      '/v1/workspaces/ws-1/agents/sess-456/approvals/app-123/grant',
      { reason: 'Approved safe modification' },
      undefined
    );
    expect(result.status).toBe('granted');
    expect(result.reason).toBe('Approved safe modification');
  });

  it('calls denyApproval with correct URL and reason payload', async () => {
    const mockApproval: AgentApproval = {
      id: 'app-123',
      session_id: 'sess-456',
      tool_call_id: 'tc-789',
      tool_name: 'terminal.execute',
      arguments_hash: 'sha256-hash',
      status: 'denied',
      requested_by: 'agent',
      decided_by: 'user-1',
      reason: 'Command not permitted',
      requested_at: '2026-09-03T12:00:00Z',
      decided_at: '2026-09-03T12:01:00Z',
      expires_at: null,
      metadata: {},
    };

    const postSpy = vi
      .spyOn(apiClient, 'post')
      .mockResolvedValue(mockApproval);

    const result = await agentService.denyApproval(
      'ws-1',
      'sess-456',
      'app-123',
      { reason: 'Command not permitted' }
    );

    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(postSpy).toHaveBeenCalledWith(
      '/v1/workspaces/ws-1/agents/sess-456/approvals/app-123/deny',
      { reason: 'Command not permitted' },
      undefined
    );
    expect(result.status).toBe('denied');
  });

  it('propagates API error when approval call fails', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new Error('Approval hash mismatch')
    );

    await expect(
      agentService.grantApproval('ws-1', 'sess-456', 'app-123')
    ).rejects.toThrow('Approval hash mismatch');
  });
});
