'use client';

import React from 'react';
import { parseUnifiedDiff } from '../../lib/utils/diff-parser';
import type { FileChangeOperation } from '../../lib/api/types';
import { FileCode, Plus, Minus } from 'lucide-react';

interface DiffViewerProps {
  readonly diff: string;
  readonly filePath?: string;
  readonly operation?: FileChangeOperation;
}

export function DiffViewer({ diff, filePath, operation }: DiffViewerProps) {
  const parsed = parseUnifiedDiff(diff);

  if (!diff || parsed.hunks.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-8 text-center text-[var(--forge-text-secondary)]">
        <FileCode className="mx-auto h-7 w-7 text-[var(--forge-text-muted)] mb-2" />
        <p className="text-xs">No diff content available for this file.</p>
      </div>
    );
  }

  const displayPath = filePath || parsed.toFile || parsed.fromFile || 'unknown';

  return (
    <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] overflow-hidden shadow-xs">
      {/* File Header */}
      <div className="flex items-center justify-between border-b border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-4 py-2">
        <div className="flex items-center space-x-2 min-w-0">
          <FileCode className="h-4 w-4 shrink-0 text-[var(--forge-text-secondary)]" />
          <span className="font-mono text-xs font-semibold text-[var(--forge-text-primary)] truncate">
            {displayPath}
          </span>
          {operation && (
            <span
              className={`rounded px-1.5 py-0.2 text-[10px] font-semibold uppercase tracking-wider ${
                operation === 'ADDED'
                  ? 'bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)]'
                  : operation === 'DELETED'
                  ? 'bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border border-[var(--forge-danger-border)]'
                  : 'bg-[var(--forge-surface)] text-[var(--forge-text-secondary)] border border-[var(--forge-border)]'
              }`}
            >
              {operation}
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          {parsed.additions > 0 && (
            <span className="flex items-center text-[var(--forge-success)]">
              <Plus className="h-3 w-3 mr-0.5" />
              {parsed.additions}
            </span>
          )}
          {parsed.deletions > 0 && (
            <span className="flex items-center text-[var(--forge-danger)]">
              <Minus className="h-3 w-3 mr-0.5" />
              {parsed.deletions}
            </span>
          )}
        </div>
      </div>

      {/* Diff Table */}
      <div className="overflow-x-auto font-mono text-xs leading-5 select-text">
        {parsed.hunks.map((hunk, hunkIdx) => (
          <div key={`hunk-${hunkIdx}`} className="border-b border-[var(--forge-border-subtle)] last:border-b-0">
            {/* Hunk Header */}
            <div className="bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] px-4 py-1 text-[11px] font-medium border-y border-[var(--forge-border-subtle)] select-none">
              {hunk.header}
            </div>

            {/* Hunk Lines */}
            <table className="w-full border-collapse">
              <tbody>
                {hunk.lines.map((line, lineIdx) => {
                  const isAdd = line.type === 'add';
                  const isDelete = line.type === 'delete';

                  const rowBg = isAdd
                    ? 'bg-[var(--forge-success-surface)] text-[var(--forge-text-primary)]'
                    : isDelete
                    ? 'bg-[var(--forge-danger-surface)] text-[var(--forge-text-primary)]'
                    : 'hover:bg-[var(--forge-surface-secondary)] text-[var(--forge-text-secondary)]';

                  const prefixColor = isAdd
                    ? 'text-[var(--forge-success)] font-semibold'
                    : isDelete
                    ? 'text-[var(--forge-danger)] font-semibold'
                    : 'text-[var(--forge-text-muted)]';

                  return (
                    <tr key={`line-${hunkIdx}-${lineIdx}`} className={`group ${rowBg}`}>
                      {/* Old Line Number */}
                      <td className="w-10 select-none px-2 py-0.5 text-right font-mono text-[10px] text-[var(--forge-text-muted)] border-r border-[var(--forge-border-subtle)]">
                        {line.oldLineNumber ?? ''}
                      </td>

                      {/* New Line Number */}
                      <td className="w-10 select-none px-2 py-0.5 text-right font-mono text-[10px] text-[var(--forge-text-muted)] border-r border-[var(--forge-border-subtle)]">
                        {line.newLineNumber ?? ''}
                      </td>

                      {/* Operation Marker (+, -, space) */}
                      <td className={`w-6 select-none px-1.5 py-0.5 text-center font-mono ${prefixColor}`}>
                        {line.type === 'add' ? '+' : line.type === 'delete' ? '-' : ' '}
                      </td>

                      {/* Code Content */}
                      <td className="px-2 py-0.5 font-mono whitespace-pre overflow-x-auto">
                        <span>{line.content}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
