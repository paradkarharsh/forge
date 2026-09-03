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
          icon: <Clock className="h-3.5 w-3.5 text-zinc-400" />,
          title: 'Session Created',
          description: 'Agent session initialized in workspace',
          color: 'text-zinc-400',
        };
      case 'agent.planning_started':
        return {
          icon: <Compass className="h-3.5 w-3.5 text-blue-400" />,
          title: 'Planning Started',
          description: 'Analyzing repository structure and context',
          color: 'text-blue-400',
        };
      case 'agent.plan_created':
        return {
          icon: <FileCheck className="h-3.5 w-3.5 text-indigo-400" />,
          title: 'Execution Plan Formulated',
          description: 'Step breakdown generated for agent execution',
          color: 'text-indigo-400',
        };
      case 'agent.running':
        return {
          icon: <Play className="h-3.5 w-3.5 text-indigo-400" />,
          title: 'Execution In Progress',
          description: 'Executing scheduled tasks and tools',
          color: 'text-indigo-400',
        };
      case 'agent.approval_requested':
        return {
          icon: <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />,
          title: 'Approval Required',
          description: 'Execution paused awaiting human authorization',
          color: 'text-amber-400',
        };
      case 'agent.approval_granted':
        return {
          icon: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
          title: 'Approval Granted',
          description: 'Resuming agent execution',
          color: 'text-emerald-400',
        };
      case 'agent.approval_denied':
        return {
          icon: <XCircle className="h-3.5 w-3.5 text-rose-400" />,
          title: 'Approval Denied',
          description: 'Tool execution rejected by user',
          color: 'text-rose-400',
        };
      case 'agent.completed':
        return {
          icon: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
          title: 'Agent Completed',
          description: 'All steps executed successfully',
          color: 'text-emerald-400',
        };
      case 'agent.cancelled':
        return {
          icon: <Ban className="h-3.5 w-3.5 text-zinc-400" />,
          title: 'Execution Cancelled',
          description: 'Session stopped by user request',
          color: 'text-zinc-400',
        };
      case 'agent.failed':
        return {
          icon: <XCircle className="h-3.5 w-3.5 text-rose-400" />,
          title: 'Execution Failed',
          description: String(event.data?.error || event.data?.reason || 'An unexpected error occurred'),
          color: 'text-rose-400',
        };
      default:
        return {
          icon: <Clock className="h-3.5 w-3.5 text-zinc-500" />,
          title: event.event_type.replace('agent.', '').replace(/_/g, ' '),
          description: '',
          color: 'text-zinc-400',
        };
    }
  };

  const meta = getEventMeta();

  return (
    <div className="flex items-center justify-between gap-3 py-1 px-3 rounded-md bg-zinc-900/30 border border-zinc-800/40 text-xs">
      <div className="flex items-center gap-2 min-w-0">
        <div className="shrink-0">{meta.icon}</div>
        <span className={`font-medium capitalize ${meta.color}`}>
          {meta.title}
        </span>
        {meta.description && (
          <span className="text-zinc-500 truncate hidden sm:inline">
            — {meta.description}
          </span>
        )}
      </div>
      <span className="text-[11px] font-mono text-zinc-500 shrink-0">
        {formatRelativeTime(event.timestamp)}
      </span>
    </div>
  );
}
