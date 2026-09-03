'use client';

import { AlertTriangle, Loader2 } from 'lucide-react';
import { useEffect } from 'react';

interface CancelModalProps {
  readonly isOpen: boolean;
  readonly isCancelling: boolean;
  readonly objective: string;
  readonly onConfirm: () => Promise<void>;
  readonly onClose: () => void;
}

export function CancelModal({
  isOpen,
  isCancelling,
  objective,
  onConfirm,
  onClose,
}: CancelModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isCancelling) {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, isCancelling, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cancel-modal-title"
    >
      <div className="w-full max-w-md rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 shadow-xl space-y-4 text-[var(--forge-text-primary)]">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border border-[var(--forge-danger-border)]">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div className="space-y-1">
            <h2 id="cancel-modal-title" className="text-sm font-semibold text-[var(--forge-text-primary)]">
              Cancel Agent Execution?
            </h2>
            <p className="text-xs text-[var(--forge-text-secondary)] leading-relaxed">
              Are you sure you want to stop this agent? Any active tool execution will be terminated immediately. This action cannot be undone.
            </p>
          </div>
        </div>

        <div className="rounded border border-[var(--forge-border-subtle)] bg-[var(--forge-surface-secondary)] p-2.5 text-xs text-[var(--forge-text-secondary)] line-clamp-2">
          <span className="font-medium text-[var(--forge-text-primary)]">Objective: </span>
          {objective}
        </div>

        <div className="flex items-center justify-end gap-2.5 pt-1">
          <button
            type="button"
            disabled={isCancelling}
            onClick={onClose}
            className="rounded border border-[var(--forge-border)] px-3 py-1.5 text-xs font-medium text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:border-[var(--forge-border-highlight)] transition-colors disabled:opacity-50"
          >
            Keep Running
          </button>
          <button
            type="button"
            disabled={isCancelling}
            onClick={onConfirm}
            className="inline-flex items-center gap-1.5 rounded border border-[var(--forge-danger-border)] bg-[var(--forge-danger-surface)] hover:bg-[var(--forge-danger-border)] px-3.5 py-1.5 text-xs font-medium text-[var(--forge-danger)] hover:text-white shadow-xs transition-colors disabled:opacity-50"
          >
            {isCancelling ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Cancelling...</span>
              </>
            ) : (
              <span>Confirm Cancellation</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
