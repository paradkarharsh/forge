import { describe, it, expect } from 'vitest';
import { extractChangedFiles } from '../lib/utils/changed-files';
import type { AgentToolCall } from '../lib/api/types';

describe('Changed Files Extraction Utility', () => {
  it('extracts created, modified, and deleted files from completed tool calls', () => {
    const mockToolCalls: AgentToolCall[] = [
      {
        id: 'tc-1',
        session_id: 'sess-1',
        step_id: 'step-1',
        tool_name: 'file.create',
        arguments: { path: 'src/main.ts', content: 'console.log("hello");' },
        risk_level: 'low',
        status: 'completed',
        approval_id: null,
        output: 'Created file src/main.ts\nDiff:\n--- /dev/null\n+++ b/src/main.ts\n@@ -0,0 +1,1 @@\n+console.log("hello");',
        error_message: null,
        duration_ms: 12,
        created_at: '2026-09-03T12:00:00Z',
        started_at: '2026-09-03T12:00:01Z',
        completed_at: '2026-09-03T12:00:02Z',
        metadata: {},
      },
      {
        id: 'tc-2',
        session_id: 'sess-1',
        step_id: 'step-2',
        tool_name: 'file.modify',
        arguments: { path: 'README.md', content: '# Forge' },
        risk_level: 'high',
        status: 'completed',
        approval_id: null,
        output: 'Modified README.md\nDiff:\n--- a/README.md\n+++ b/README.md\n@@ -1,1 +1,2 @@\n-# Old Title\n+# Forge\n+New line',
        error_message: null,
        duration_ms: 15,
        created_at: '2026-09-03T12:01:00Z',
        started_at: '2026-09-03T12:01:01Z',
        completed_at: '2026-09-03T12:01:02Z',
        metadata: {},
      },
      {
        id: 'tc-3',
        session_id: 'sess-1',
        step_id: 'step-3',
        tool_name: 'file.delete',
        arguments: { path: 'temp.txt' },
        risk_level: 'high',
        status: 'completed',
        approval_id: null,
        output: 'Deleted temp.txt\nDiff:\n--- a/temp.txt\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-temporary content',
        error_message: null,
        duration_ms: 8,
        created_at: '2026-09-03T12:02:00Z',
        started_at: '2026-09-03T12:02:01Z',
        completed_at: '2026-09-03T12:02:02Z',
        metadata: {},
      },
    ];

    const result = extractChangedFiles(mockToolCalls);

    expect(result).toHaveLength(3);

    const mainFile = result.find((f) => f.path === 'src/main.ts');
    expect(mainFile?.operation).toBe('ADDED');
    expect(mainFile?.additions).toBe(1);
    expect(mainFile?.deletions).toBe(0);

    const readmeFile = result.find((f) => f.path === 'README.md');
    expect(readmeFile?.operation).toBe('MODIFIED');
    expect(readmeFile?.additions).toBe(2);
    expect(readmeFile?.deletions).toBe(1);

    const tempFile = result.find((f) => f.path === 'temp.txt');
    expect(tempFile?.operation).toBe('DELETED');
    expect(tempFile?.deletions).toBe(1);
  });

  it('ignores pending, running, or failed tool calls', () => {
    const mockToolCalls: AgentToolCall[] = [
      {
        id: 'tc-pending',
        session_id: 'sess-1',
        step_id: null,
        tool_name: 'file.create',
        arguments: { path: 'pending.txt', content: 'test' },
        risk_level: 'high',
        status: 'pending',
        approval_id: null,
        output: null,
        error_message: null,
        duration_ms: null,
        created_at: '2026-09-03T12:00:00Z',
        started_at: null,
        completed_at: null,
        metadata: {},
      },
      {
        id: 'tc-failed',
        session_id: 'sess-1',
        step_id: null,
        tool_name: 'file.modify',
        arguments: { path: 'fail.txt', content: 'test' },
        risk_level: 'high',
        status: 'failed',
        output: null,
        error_message: 'write error',
        approval_id: null,
        duration_ms: 10,
        created_at: '2026-09-03T12:00:00Z',
        started_at: '2026-09-03T12:00:01Z',
        completed_at: '2026-09-03T12:00:02Z',
        metadata: {},
      },
    ];

    const result = extractChangedFiles(mockToolCalls);
    expect(result).toHaveLength(0);
  });

  it('preserves ADDED operation if file was created then modified', () => {
    const mockToolCalls: AgentToolCall[] = [
      {
        id: 'tc-create',
        session_id: 'sess-1',
        step_id: null,
        tool_name: 'file.create',
        arguments: { path: 'test.ts', content: 'initial' },
        risk_level: 'high',
        status: 'completed',
        approval_id: null,
        output: 'Created file test.ts',
        error_message: null,
        duration_ms: 10,
        created_at: '2026-09-03T12:00:00Z',
        started_at: '2026-09-03T12:00:01Z',
        completed_at: '2026-09-03T12:00:02Z',
        metadata: {},
      },
      {
        id: 'tc-modify',
        session_id: 'sess-1',
        step_id: null,
        tool_name: 'file.modify',
        arguments: { path: 'test.ts', content: 'updated' },
        risk_level: 'high',
        status: 'completed',
        approval_id: null,
        output: 'Modified file test.ts\nDiff:\n--- a/test.ts\n+++ b/test.ts\n@@ -1,1 +1,1 @@\n-initial\n+updated',
        error_message: null,
        duration_ms: 10,
        created_at: '2026-09-03T12:01:00Z',
        started_at: '2026-09-03T12:01:01Z',
        completed_at: '2026-09-03T12:01:02Z',
        metadata: {},
      },
    ];

    const result = extractChangedFiles(mockToolCalls);
    expect(result).toHaveLength(1);
    expect(result[0].path).toBe('test.ts');
    expect(result[0].operation).toBe('ADDED');
  });
});
