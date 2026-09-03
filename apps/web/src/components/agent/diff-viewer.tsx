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
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-8 text-center text-neutral-400">
        <FileCode className="mx-auto h-8 w-8 text-neutral-500 mb-2" />
        <p className="text-sm">No diff content available for this file.</p>
      </div>
    );
  }

  const displayPath = filePath || parsed.toFile || parsed.fromFile || 'unknown';

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-950/90 overflow-hidden shadow-lg">
      {/* File Header */}
      <div className="flex items-center justify-between border-b border-neutral-800/80 bg-neutral-900/80 px-4 py-2.5">
        <div className="flex items-center space-x-2 min-w-0">
          <FileCode className="h-4 w-4 shrink-0 text-sky-400" />
          <span className="font-mono text-xs font-semibold text-neutral-200 truncate">
            {displayPath}
          </span>
          {operation && (
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                operation === 'ADDED'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  : operation === 'DELETED'
                  ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                  : 'bg-sky-500/10 text-sky-400 border border-sky-500/30'
              }`}
            >
              {operation}
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          {parsed.additions > 0 && (
            <span className="flex items-center text-emerald-400">
              <Plus className="h-3 w-3 mr-0.5" />
              {parsed.additions}
            </span>
          )}
          {parsed.deletions > 0 && (
            <span className="flex items-center text-rose-400">
              <Minus className="h-3 w-3 mr-0.5" />
              {parsed.deletions}
            </span>
          )}
        </div>
      </div>

      {/* Diff Table */}
      <div className="overflow-x-auto font-mono text-xs leading-5 select-text">
        {parsed.hunks.map((hunk, hunkIdx) => (
          <div key={`hunk-${hunkIdx}`} className="border-b border-neutral-900 last:border-b-0">
            {/* Hunk Header */}
            <div className="bg-sky-950/20 text-sky-400/80 px-4 py-1 text-[11px] font-semibold border-y border-neutral-800/40 select-none">
              {hunk.header}
            </div>

            {/* Hunk Lines */}
            <table className="w-full border-collapse">
              <tbody>
                {hunk.lines.map((line, lineIdx) => {
                  const isAdd = line.type === 'add';
                  const isDelete = line.type === 'delete';

                  const rowBg = isAdd
                    ? 'bg-emerald-950/20 hover:bg-emerald-950/30 text-emerald-200'
                    : isDelete
                    ? 'bg-rose-950/20 hover:bg-rose-950/30 text-rose-200'
                    : 'hover:bg-neutral-900/40 text-neutral-300';

                  const prefixColor = isAdd
                    ? 'text-emerald-400 font-bold'
                    : isDelete
                    ? 'text-rose-400 font-bold'
                    : 'text-neutral-600';

                  return (
                    <tr key={`line-${hunkIdx}-${lineIdx}`} className={`group ${rowBg}`}>
                      {/* Old Line Number */}
                      <td className="w-10 select-none px-2 py-0.5 text-right font-mono text-[10px] text-neutral-600 group-hover:text-neutral-500 border-r border-neutral-800/40">
                        {line.oldLineNumber ?? ''}
                      </td>

                      {/* New Line Number */}
                      <td className="w-10 select-none px-2 py-0.5 text-right font-mono text-[10px] text-neutral-600 group-hover:text-neutral-500 border-r border-neutral-800/40">
                        {line.newLineNumber ?? ''}
                      </td>

                      {/* Marker (+, -, ' ') */}
                      <td className={`w-5 select-none px-1 py-0.5 text-center ${prefixColor}`}>
                        {isAdd ? '+' : isDelete ? '-' : ' '}
                      </td>

                      {/* Line content (pure text rendering, zero XSS vulnerability) */}
                      <td className="px-2 py-0.5 whitespace-pre font-mono">
                        {line.content}
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
