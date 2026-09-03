import type { AgentToolCall, ChangedFile, FileChangeOperation } from '../api/types';
import { parseUnifiedDiff } from './diff-parser';

/**
 * Extract diff text from tool output if output starts with or contains 'Diff:\n'.
 */
function extractDiff(output: string | null): string | undefined {
  if (!output) return undefined;
  const marker = 'Diff:\n';
  const idx = output.indexOf(marker);
  if (idx !== -1) {
    return output.slice(idx + marker.length).trim();
  }
  if (output.startsWith('--- ') || output.startsWith('@@ ')) {
    return output;
  }
  return undefined;
}

/**
 * Derives the list of confirmed changed repository files from executed tool calls.
 */
export function extractChangedFiles(toolCalls: readonly AgentToolCall[]): ChangedFile[] {
  const fileMap = new Map<string, ChangedFile>();

  for (const tc of toolCalls) {
    if (tc.status !== 'completed') continue;

    let operation: FileChangeOperation | null = null;
    if (tc.tool_name === 'file.create') {
      operation = 'ADDED';
    } else if (tc.tool_name === 'file.modify') {
      operation = 'MODIFIED';
    } else if (tc.tool_name === 'file.delete') {
      operation = 'DELETED';
    }

    if (!operation) continue;

    // Extract path from arguments or metadata
    const rawPath =
      (tc.arguments?.path as string | undefined) ||
      (tc.metadata?.path as string | undefined);

    if (!rawPath || typeof rawPath !== 'string') continue;
    const cleanPath = rawPath.replace(/^[/\\]+/, '');

    // Extract diff from output or data
    const diffText =
      extractDiff(tc.output) ||
      (typeof tc.metadata?.diff === 'string' ? tc.metadata.diff : undefined);

    let additions = 0;
    let deletions = 0;

    if (diffText) {
      const parsed = parseUnifiedDiff(diffText);
      additions = parsed.additions;
      deletions = parsed.deletions;
    } else if (operation === 'ADDED' && typeof tc.arguments?.content === 'string') {
      additions = tc.arguments.content.split('\n').length;
    }

    // Preserve initial ADDED status if subsequent edit occurred
    const existing = fileMap.get(cleanPath);
    const finalOperation = existing?.operation === 'ADDED' && operation === 'MODIFIED' ? 'ADDED' : operation;

    fileMap.set(cleanPath, {
      path: cleanPath,
      operation: finalOperation,
      additions: (existing?.additions || 0) + additions,
      deletions: (existing?.deletions || 0) + deletions,
      diff: diffText || existing?.diff,
      toolName: tc.tool_name,
      timestamp: tc.completed_at || tc.started_at || tc.created_at,
    });
  }

  return Array.from(fileMap.values());
}
