'use client';

import {
  Ban,
  CheckCircle2,
  Clock,
  Compass,
  FileCheck,
  Play,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import type { AgentEvent } from '../../lib/api/types';
import { formatRelativeTime } from '../../lib/utils/formatters';

interface LifecycleEventItemProps {
  readonly event: AgentEvent;
}

export function LifecycleEventItem({ event }: LifecycleEventItemProps) {
  const getEventMeta = () => {
    switch (event.event_type) {
      case 'agent.created':
        return {
          icon: <Clock className="h-3 w-3 text-[var(--forge-text-muted)]" />,
          title: 'Session Created',
          description: 'Agent session initialized in workspace',
          color: 'text-[var(--forge-text-muted)]',
        };
      case 'agent.planning_started':
        return {
          icon: <Compass className="h-3 w-3 text-[var(--forge-accent)]" />,
          title: 'Planning Started',
          description: 'Analyzing repository structure and context',
          color: 'text-[var(--forge-accent)]',
        };
      case 'agent.plan_created':
        return {
          icon: <FileCheck className="h-3 w-3 text-[var(--forge-accent)]" />,
          title: 'Execution Plan Formulated',
          description: 'Step breakdown generated for agent execution',
          color: 'text-[var(--forge-accent)]',
        };
      case 'agent.running':
        return {
          icon: <Play className="h-3 w-3 text-[var(--forge-success)]" />,
          title: 'Execution In Progress',
          description: 'Executing scheduled tasks and tools',
          color: 'text-[var(--forge-success)]',
        };
      case 'agent.approval_requested':
        return {
          icon: <ShieldAlert className="h-3 w-3 text-[var(--forge-warning)]" />,
          title: 'Approval Required',
          description: 'Execution paused awaiting human authorization',
          color: 'text-[var(--forge-warning)]',
        };
      case 'agent.approval_granted':
        return {
          icon: <CheckCircle2 className="h-3 w-3 text-[var(--forge-success)]" />,
          title: 'Approval Granted',
          description: 'Resuming agent execution',
          color: 'text-[var(--forge-success)]',
        };
      case 'agent.approval_denied':
        return {
          icon: <XCircle className="h-3 w-3 text-[var(--forge-danger)]" />,
          title: 'Approval Denied',
          description: 'Tool execution rejected by user',
          color: 'text-[var(--forge-danger)]',
        };
      case 'agent.completed':
        return {
          icon: <CheckCircle2 className="h-3 w-3 text-[var(--forge-success)]" />,
          title: 'Agent Completed',
          description: 'All steps executed successfully',
          color: 'text-[var(--forge-success)]',
        };
      case 'agent.cancelled':
        return {
          icon: <Ban className="h-3 w-3 text-[var(--forge-text-muted)]" />,
          title: 'Execution Cancelled',
          description: 'Session stopped by user request',
          color: 'text-[var(--forge-text-muted)]',
        };
      case 'agent.failed':
        return {
          icon: <XCircle className="h-3 w-3 text-[var(--forge-danger)]" />,
          title: 'Execution Failed',
          description: String(event.data?.error || event.data?.reason || 'An unexpected error occurred'),
          color: 'text-[var(--forge-danger)]',
        };
      default:
        return {
          icon: <Clock className="h-3 w-3 text-[var(--forge-text-muted)]" />,
          title: event.event_type.replace('agent.', '').replace(/_/g, ' '),
          description: '',
          color: 'text-[var(--forge-text-secondary)]',
        };
    }
  };

  const meta = getEventMeta();

  return (
    <div className="flex items-center justify-between gap-2.5 py-1 px-2.5 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border-subtle)] text-xs">
      <div className="flex items-center gap-2 min-w-0">
        <div className="shrink-0">{meta.icon}</div>
        <span className={`font-medium capitalize text-[11px] ${meta.color}`}>
          {meta.title}
        </span>
        {meta.description && (
          <span className="text-[11px] text-[var(--forge-text-muted)] truncate hidden sm:inline">
            — {meta.description}
          </span>
        )}
      </div>
      <span className="text-[10px] font-mono text-[var(--forge-text-muted)] shrink-0">
        {formatRelativeTime(event.timestamp)}
      </span>
    </div>
  );
}
