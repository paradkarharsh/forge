'use client';

import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import type { AgentStep } from '../../lib/api/types';
import { formatRelativeTime } from '../../lib/utils/formatters';

interface StepItemProps {
  readonly step: AgentStep;
}

export function StepItem({ step }: StepItemProps) {
  const getStatusIcon = () => {
    switch (step.status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-[var(--forge-success)]" />;
      case 'running':
        return <Loader2 className="h-4 w-4 text-[var(--forge-accent)] animate-spin" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-[var(--forge-danger)]" />;
      case 'pending':
      default:
        return <Circle className="h-4 w-4 text-[var(--forge-text-muted)]" />;
    }
  };

  const getStatusBadge = () => {
    const styles: Record<string, string> = {
      completed: 'bg-[var(--forge-success-surface)] text-[var(--forge-success)] border-[var(--forge-success-border)]',
      running: 'bg-[var(--forge-surface-secondary)] text-[var(--forge-accent)] border-[var(--forge-border)]',
      failed: 'bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border-[var(--forge-danger-border)]',
      pending: 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] border-[var(--forge-border)]',
    };
    const style = styles[step.status] || styles.pending;
    return (
      <span className={`text-[10px] uppercase font-mono px-1.5 py-0.2 rounded border ${style}`}>
        {step.status}
      </span>
    );
  };

  return (
    <div className="relative flex items-start gap-3 rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3 transition-colors hover:border-[var(--forge-border-highlight)]">
      <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[var(--forge-surface-secondary)] text-xs font-mono font-medium text-[var(--forge-text-secondary)] border border-[var(--forge-border-subtle)]">
        {step.sequence}
      </div>

      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {getStatusIcon()}
            <span className="text-xs font-medium text-[var(--forge-text-primary)] truncate">
              {step.objective}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {getStatusBadge()}
            <span className="text-[10px] font-mono text-[var(--forge-text-muted)]">
              {formatRelativeTime(step.created_at)}
            </span>
          </div>
        </div>

        {Boolean(step.metadata?.summary) && (
          <p className="text-xs text-[var(--forge-text-secondary)] leading-relaxed">
            {String(step.metadata.summary)}
          </p>
        )}

        {Boolean(step.metadata?.error) && (
          <div className="mt-2 rounded border border-[var(--forge-danger-border)] bg-[var(--forge-danger-surface)] p-2 text-xs font-mono text-[var(--forge-danger)]">
            {String(step.metadata.error)}
          </div>
        )}
      </div>
    </div>
  );
}
