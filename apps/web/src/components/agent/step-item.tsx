'use client';

import { CheckCircle2, Circle, Clock, Loader2, XCircle } from 'lucide-react';
import type { AgentStep } from '../../lib/api/types';
import { formatRelativeTime } from '../../lib/utils/formatters';

interface StepItemProps {
  readonly step: AgentStep;
}

export function StepItem({ step }: StepItemProps) {
  const getStatusIcon = () => {
    switch (step.status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
      case 'running':
        return <Loader2 className="h-4 w-4 text-indigo-400 animate-spin" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-rose-400" />;
      case 'pending':
      default:
        return <Circle className="h-4 w-4 text-zinc-600" />;
    }
  };

  const getStatusBadge = () => {
    const styles: Record<string, string> = {
      completed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
      running: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
      failed: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
      pending: 'bg-zinc-800 text-zinc-400 border-zinc-700',
    };
    const style = styles[step.status] || styles.pending;
    return (
      <span className={`text-[10px] uppercase font-mono px-1.5 py-0.5 rounded border ${style}`}>
        {step.status}
      </span>
    );
  };

  return (
    <div className="relative flex items-start gap-3 rounded-lg border border-zinc-800/80 bg-zinc-900/40 p-3.5 transition-colors hover:border-zinc-700">
      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-zinc-800 text-xs font-mono font-medium text-zinc-300">
        {step.sequence}
      </div>

      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {getStatusIcon()}
            <span className="text-sm font-medium text-zinc-200 truncate">
              {step.objective}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {getStatusBadge()}
            <span className="text-[11px] font-mono text-zinc-500">
              {formatRelativeTime(step.created_at)}
            </span>
          </div>
        </div>

        {step.started_at && (
          <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-500 pt-0.5">
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span>Started: {new Date(step.started_at).toLocaleTimeString()}</span>
            </span>
            {step.completed_at && (
              <span>Completed: {new Date(step.completed_at).toLocaleTimeString()}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
