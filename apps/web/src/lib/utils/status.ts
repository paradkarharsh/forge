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
    badgeClass: 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-secondary)] border-[var(--forge-border)]',
    dotClass: 'bg-[var(--forge-text-muted)]',
    iconName: 'clock',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: false,
    isCancellable: true,
  },
  planning: {
    label: 'Planning',
    description: 'Agent is formulating an execution plan with context retrieval',
    badgeClass: 'bg-[rgba(244,239,230,0.08)] text-[var(--forge-accent)] border-[rgba(244,239,230,0.2)]',
    dotClass: 'bg-[var(--forge-accent)] animate-pulse',
    iconName: 'brain',
    isActive: true,
    isWaitingApproval: false,
    isTerminal: false,
    isCancellable: true,
  },
  running: {
    label: 'Running',
    description: 'Agent is actively executing plan steps and invoking tools',
    badgeClass: 'bg-[var(--forge-success-surface)] text-[var(--forge-success)] border-[var(--forge-success-border)]',
    dotClass: 'bg-[var(--forge-success)] animate-pulse',
    iconName: 'play',
    isActive: true,
    isWaitingApproval: false,
    isTerminal: false,
    isCancellable: true,
  },
  waiting_for_approval: {
    label: 'Waiting for Approval',
    description: 'Execution paused awaiting human authorization for a high-risk tool call',
    badgeClass: 'bg-[var(--forge-warning-surface)] text-[var(--forge-warning)] border-[var(--forge-warning-border)]',
    dotClass: 'bg-[var(--forge-warning)] animate-ping',
    iconName: 'shield-alert',
    isActive: false,
    isWaitingApproval: true,
    isTerminal: false,
    isCancellable: true,
  },
  completed: {
    label: 'Completed',
    description: 'Agent objective successfully accomplished',
    badgeClass: 'bg-[var(--forge-success-surface)] text-[var(--forge-success)] border-[var(--forge-success-border)]',
    dotClass: 'bg-[var(--forge-success)]',
    iconName: 'check-circle',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
  failed: {
    label: 'Failed',
    description: 'Agent execution encountered an unrecoverable error',
    badgeClass: 'bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border-[var(--forge-danger-border)]',
    dotClass: 'bg-[var(--forge-danger)]',
    iconName: 'x-circle',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
  cancelled: {
    label: 'Cancelled',
    description: 'Agent execution was stopped by user request',
    badgeClass: 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] border-[var(--forge-border)]',
    dotClass: 'bg-[var(--forge-text-muted)]',
    iconName: 'slash',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
  timed_out: {
    label: 'Timed Out',
    description: 'Execution exceeded durable wall-clock or LLM call limit',
    badgeClass: 'bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border-[var(--forge-danger-border)]',
    dotClass: 'bg-[var(--forge-danger)]',
    iconName: 'timer-off',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
  expired: {
    label: 'Expired',
    description: 'Pending human approval expired without resolution',
    badgeClass: 'bg-[var(--forge-warning-surface)] text-[var(--forge-warning)] border-[var(--forge-warning-border)]',
    dotClass: 'bg-[var(--forge-warning)]',
    iconName: 'calendar-x',
    isActive: false,
    isWaitingApproval: false,
    isTerminal: true,
    isCancellable: false,
  },
};

export function getStatusConfig(status: AgentStatus | string): StatusConfig {
  const normalized = (status || '').toLowerCase() as AgentStatus;
  return STATUS_CONFIGS[normalized] || STATUS_CONFIGS.created;
}

export function isTerminalStatus(status: AgentStatus | string): boolean {
  return getStatusConfig(status).isTerminal;
}

export function isCancellableStatus(status: AgentStatus | string): boolean {
  return getStatusConfig(status).isCancellable;
}

export function isWaitingForApproval(status: AgentStatus | string): boolean {
  return getStatusConfig(status).isWaitingApproval;
}

export function isActiveStatus(status: AgentStatus | string): boolean {
  return getStatusConfig(status).isActive;
}
