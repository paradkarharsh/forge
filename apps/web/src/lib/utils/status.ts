import type { AgentStatus } from '../api/types';

export interface StatusConfig {
  readonly label: string;
  readonly description: string;
  readonly badgeClass: string;
  readonly dotClass: string;
  readonly iconName: 'clock' | 'brain' | 'play' | 'shield-alert' | 'check-circle' | 'x-circle' | 'slash' | 'timer-off' | 'calendar-x';
  readonly isActive: boolean;
  readonly isWaitingApproval: boolean;
  readonly isTerminal: boolean;
  readonly isCancellable: boolean;
}

export const STATUS_CONFIGS: Record<AgentStatus, StatusConfig> = {
  created: {
    label: 'Created',
    description: 'Agent session initialized and awaiting execution dispatch',
    badgeClass: 'bg-zinc-500/10 text-zinc-400 border-zinc-700/50',
    dotClass: 'bg-zinc-400',
    iconName: 'clock',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: false,
    isCancellable: true,
  },
  planning: {
    label: 'Planning',
    description: 'Agent is formulating an execution plan with context retrieval',
    badgeClass: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    dotClass: 'bg-blue-400 animate-pulse',
    iconName: 'brain',
    isActive: true,
    isWaitingApproval: false,
    isTerminal: false,
    isCancellable: true,
  },
  running: {
    label: 'Running',
    description: 'Agent is actively executing plan steps and invoking tools',
    badgeClass: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
    dotClass: 'bg-indigo-400 animate-pulse',
    iconName: 'play',
    isActive: true,
    isWaitingApproval: false,
    isTerminal: false,
    isCancellable: true,
  },
  waiting_for_approval: {
    label: 'Waiting for Approval',
    description: 'Execution paused awaiting human authorization for a high-risk tool call',
    badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    dotClass: 'bg-amber-400 animate-ping',
    iconName: 'shield-alert',
    isActive: false,
    isWaitingApproval: true,
    isTerminal: false,
    isCancellable: true,
  },
  completed: {
    label: 'Completed',
    description: 'Agent objective successfully accomplished',
    badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    dotClass: 'bg-emerald-400',
    iconName: 'check-circle',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
  failed: {
    label: 'Failed',
    description: 'Agent execution encountered an unrecoverable error',
    badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    dotClass: 'bg-rose-400',
    iconName: 'x-circle',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
  cancelled: {
    label: 'Cancelled',
    description: 'Agent execution was stopped by user request',
    badgeClass: 'bg-zinc-500/10 text-zinc-400 border-zinc-700/50',
    dotClass: 'bg-zinc-400',
    iconName: 'slash',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
  timed_out: {
    label: 'Timed Out',
    description: 'Execution exceeded durable wall-clock or LLM call limit',
    badgeClass: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    dotClass: 'bg-orange-400',
    iconName: 'timer-off',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
  expired: {
    label: 'Expired',
    description: 'Approval deadline passed without human decision',
    badgeClass: 'bg-zinc-500/10 text-zinc-400 border-zinc-700/50',
    dotClass: 'bg-zinc-400',
    iconName: 'calendar-x',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
};

export function getStatusConfig(status: AgentStatus | string): StatusConfig {
  const normalized = (status || 'created').toLowerCase() as AgentStatus;
  return STATUS_CONFIGS[normalized] || STATUS_CONFIGS.created;
}
