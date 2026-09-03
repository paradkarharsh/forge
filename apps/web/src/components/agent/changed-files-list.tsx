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
      <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-12 text-center">
        <FileCode className="mx-auto h-8 w-8 text-[var(--forge-text-muted)] mb-3" />
        <h4 className="text-xs font-semibold text-[var(--forge-text-primary)]">No changes recorded</h4>
        <p className="mt-1 text-xs text-[var(--forge-text-secondary)] max-w-sm mx-auto">
          Files created, modified, or deleted during agent execution will be listed here with unified diffs.
        </p>
      </div>
    );
  }

  const totalAdditions = files.reduce((acc, f) => acc + f.additions, 0);
  const totalDeletions = files.reduce((acc, f) => acc + f.deletions, 0);

  return (
    <div className="space-y-3">
      {/* Header Summary */}
      <div className="flex items-center justify-between rounded-md border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-4 py-2.5">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-[var(--forge-text-primary)]">
            {files.length} {files.length === 1 ? 'file' : 'files'} changed
          </span>
        </div>
        <div className="flex items-center space-x-3 font-mono text-xs">
          {totalAdditions > 0 && (
            <span className="flex items-center text-[var(--forge-success)]">
              <Plus className="h-3 w-3 mr-0.5" />
              {totalAdditions}
            </span>
          )}
          {totalDeletions > 0 && (
            <span className="flex items-center text-[var(--forge-danger)]">
              <Minus className="h-3 w-3 mr-0.5" />
              {totalDeletions}
            </span>
          )}
        </div>
      </div>

      {/* Files List */}
      <div className="divide-y divide-[var(--forge-border-subtle)] rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] overflow-hidden">
        {files.map((file) => {
          const isSelected = selectedPath === file.path;

          const opColor =
            file.operation === 'ADDED'
              ? 'text-[var(--forge-success)] bg-[var(--forge-success-surface)] border-[var(--forge-success-border)]'
              : file.operation === 'DELETED'
              ? 'text-[var(--forge-danger)] bg-[var(--forge-danger-surface)] border-[var(--forge-danger-border)]'
              : 'text-[var(--forge-accent)] bg-[var(--forge-surface-secondary)] border-[var(--forge-border)]';

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
              className={`w-full flex items-center justify-between px-4 py-3 text-left transition-colors ${
                isSelected
                  ? 'bg-[var(--forge-surface-secondary)] ring-1 ring-inset ring-[var(--forge-border)]'
                  : 'hover:bg-[var(--forge-surface-secondary)]'
              }`}
            >
              <div className="flex items-center space-x-3 min-w-0 pr-4">
                <OpIcon className="h-4 w-4 shrink-0 text-[var(--forge-text-muted)]" />
                <div className="min-w-0">
                  <p className="font-mono text-xs font-medium text-[var(--forge-text-primary)] truncate">
                    {file.path}
                  </p>
                  {file.toolName && (
                    <p className="text-[11px] text-[var(--forge-text-muted)]">
                      via <span className="font-mono text-[var(--forge-text-secondary)]">{file.toolName}</span>
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-3 shrink-0">
                <span
                  className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${opColor}`}
                >
                  {file.operation}
                </span>

                <div className="flex items-center space-x-1.5 font-mono text-xs w-16 justify-end">
                  {file.additions > 0 && (
                    <span className="text-[var(--forge-success)]">+{file.additions}</span>
                  )}
                  {file.deletions > 0 && (
                    <span className="text-[var(--forge-danger)]">-{file.deletions}</span>
                  )}
                </div>

                <ChevronRight className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
