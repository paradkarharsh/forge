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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-in fade-in duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cancel-modal-title"
    >
      <div className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl space-y-4 text-zinc-100">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <h2 id="cancel-modal-title" className="text-base font-semibold text-zinc-100">
              Cancel Agent Execution?
            </h2>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Are you sure you want to stop this agent? Any active tool execution will be terminated immediately. This action cannot be undone.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/50 p-3 text-xs text-zinc-400 line-clamp-2">
          <span className="font-medium text-zinc-300">Objective: </span>
          {objective}
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            disabled={isCancelling}
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-900 hover:text-zinc-100 transition-colors disabled:opacity-50"
          >
            Keep Running
          </button>
          <button
            type="button"
            disabled={isCancelling}
            onClick={onConfirm}
            className="inline-flex items-center gap-2 rounded-lg bg-rose-600 hover:bg-rose-700 px-4 py-2 text-sm font-medium text-white shadow-xs transition-colors disabled:opacity-50"
          >
            {isCancelling ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Cancelling...</span>
              </>
            ) : (
              <span>Yes, Cancel Agent</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
