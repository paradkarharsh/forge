import { describe, it, expect } from 'vitest';
import { isTerminalStatus, type AgentSession, type AgentStatus } from '../lib/api/types';
import { extractChangedFiles } from '../lib/utils/changed-files';

describe('Session State Reconstruction & Recovery', () => {
  it('correctly identifies terminal statuses to prevent unnecessary reconnection loops', () => {
    const terminalStatuses: AgentStatus[] = [
      'completed',
      'failed',
      'cancelled',
      'timed_out',
      'expired',
    ];

    for (const status of terminalStatuses) {
      expect(isTerminalStatus(status)).toBe(true);
    }

    const activeStatuses: AgentStatus[] = [
      'created',
      'planning',
      'running',
      'waiting_for_approval',
    ];

    for (const status of activeStatuses) {
      expect(isTerminalStatus(status)).toBe(false);
    }
  });

  it('reconstructs complete session timeline and changed files from REST snapshot on page load', () => {
    const restoredSession: AgentSession = {
      id: 'sess-restore-1',
      workspace_id: 'ws-1',
      user_id: 'user-1',
      objective: 'Refactor test suite and add documentation',
      status: 'completed',
      repository_id: 'repo-1',
      conversation_id: null,
      model: 'gpt-4o',
      limits: {
        max_wall_time_seconds: 900,
        max_llm_calls: 30,
        max_tool_calls: 50,
        max_output_bytes: 65536,
        max_observation_bytes: 8192,
      },
      metrics: {
        total_llm_calls: 4,
        total_llm_retries: 0,
        total_tool_calls: 3,
        total_input_tokens: 4200,
        total_output_tokens: 850,
        wall_time_seconds: 42.5,
        estimated_cost_usd: 0.045,
      },
      usage_summary: {
        total_llm_calls: 4,
        total_llm_retries: 0,
        total_tool_calls: 3,
        total_input_tokens: 4200,
        total_output_tokens: 850,
        wall_time_seconds: 42.5,
        estimated_cost_usd: 0.045,
      },
      failure_reason: null,
      current_step: 3,
      metadata: {},
      created_at: '2026-09-03T10:00:00Z',
      started_at: '2026-09-03T10:00:01Z',
      completed_at: '2026-09-03T10:00:43Z',
      cancelled_at: null,
      last_heartbeat_at: '2026-09-03T10:00:43Z',
    };

    const restoredToolCalls = [
      {
        id: 'tc-1',
        session_id: 'sess-restore-1',
        step_id: 'step-1',
        tool_name: 'file.create',
        arguments: { path: 'docs/guide.md', content: '# Guide\nContent here' },
        risk_level: 'low' as const,
        status: 'completed' as const,
        approval_id: null,
        output: 'Created file docs/guide.md\nDiff:\n--- /dev/null\n+++ b/docs/guide.md\n@@ -0,0 +1,2 @@\n+# Guide\n+Content here',
        error_message: null,
        duration_ms: 15,
        created_at: '2026-09-03T10:00:05Z',
        started_at: '2026-09-03T10:00:06Z',
        completed_at: '2026-09-03T10:00:07Z',
        metadata: {},
      },
    ];

    expect(restoredSession.status).toBe('completed');
    expect(restoredSession.current_step).toBe(3);

    const changedFiles = extractChangedFiles(restoredToolCalls);
    expect(changedFiles).toHaveLength(1);
    expect(changedFiles[0].path).toBe('docs/guide.md');
    expect(changedFiles[0].operation).toBe('ADDED');
    expect(changedFiles[0].additions).toBe(2);
  });
});
