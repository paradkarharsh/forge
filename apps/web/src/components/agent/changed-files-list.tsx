'use client';

import React from 'react';
import type { ChangedFile } from '../../lib/api/types';
import { FileCode, FilePlus, FileEdit, FileX, Plus, Minus, ChevronRight } from 'lucide-react';

interface ChangedFilesListProps {
  readonly files: readonly ChangedFile[];
  readonly selectedPath?: string;
  readonly onSelectFile?: (file: ChangedFile) => void;
}

export function ChangedFilesList({
  files,
  selectedPath,
  onSelectFile,
}: ChangedFilesListProps) {
  if (files.length === 0) {
    return (
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-12 text-center">
        <FileCode className="mx-auto h-10 w-10 text-neutral-600 mb-3" />
        <h4 className="text-sm font-semibold text-neutral-300">No changes yet</h4>
        <p className="mt-1 text-xs text-neutral-500 max-w-sm mx-auto">
          Files created, modified, or deleted during agent execution will be listed here with live diffs.
        </p>
      </div>
    );
  }

  const totalAdditions = files.reduce((acc, f) => acc + f.additions, 0);
  const totalDeletions = files.reduce((acc, f) => acc + f.deletions, 0);

  return (
    <div className="space-y-4">
      {/* Header Summary */}
      <div className="flex items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900/60 px-4 py-3">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-white">
            {files.length} {files.length === 1 ? 'file' : 'files'} changed
          </span>
        </div>
        <div className="flex items-center space-x-3 font-mono text-xs">
          {totalAdditions > 0 && (
            <span className="flex items-center text-emerald-400">
              <Plus className="h-3 w-3 mr-0.5" />
              {totalAdditions}
            </span>
          )}
          {totalDeletions > 0 && (
            <span className="flex items-center text-rose-400">
              <Minus className="h-3 w-3 mr-0.5" />
              {totalDeletions}
            </span>
          )}
        </div>
      </div>

      {/* Files List */}
      <div className="divide-y divide-neutral-800/60 rounded-xl border border-neutral-800 bg-neutral-950/60 overflow-hidden">
        {files.map((file) => {
          const isSelected = selectedPath === file.path;

          const opColor =
            file.operation === 'ADDED'
              ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
              : file.operation === 'DELETED'
              ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
              : 'text-sky-400 bg-sky-500/10 border-sky-500/30';

          const OpIcon =
            file.operation === 'ADDED'
              ? FilePlus
              : file.operation === 'DELETED'
              ? FileX
              : FileEdit;

          return (
            <button
              key={file.path}
              type="button"
              onClick={() => onSelectFile?.(file)}
              className={`w-full flex items-center justify-between px-4 py-3.5 text-left transition-colors ${
                isSelected
                  ? 'bg-neutral-800/80 ring-1 ring-inset ring-neutral-700'
                  : 'hover:bg-neutral-900/60'
              }`}
            >
              <div className="flex items-center space-x-3 min-w-0 pr-4">
                <OpIcon className="h-4 w-4 shrink-0 text-neutral-400" />
                <div className="min-w-0">
                  <p className="font-mono text-xs font-medium text-neutral-200 truncate">
                    {file.path}
                  </p>
                  {file.toolName && (
                    <p className="text-[11px] text-neutral-500">
                      via <span className="font-mono text-neutral-400">{file.toolName}</span>
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-3 shrink-0">
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${opColor}`}>
                  {file.operation}
                </span>

                <div className="flex items-center space-x-2 font-mono text-xs">
                  {file.additions > 0 && (
                    <span className="text-emerald-400">+{file.additions}</span>
                  )}
                  {file.deletions > 0 && (
                    <span className="text-rose-400">-{file.deletions}</span>
                  )}
                </div>

                <ChevronRight className="h-4 w-4 text-neutral-600" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
