import { describe, expect, it } from 'vitest';
import {
  isCancellableStatus,
  isTerminalStatus,
  type AgentStatus,
} from '../lib/api/types';
import { getStatusConfig, STATUS_CONFIGS } from '../lib/utils/status';

describe('Status System', () => {
  const allStatuses: AgentStatus[] = [
    'created',
    'planning',
    'running',
    'waiting_for_approval',
    'completed',
    'failed',
    'cancelled',
    'timed_out',
    'expired',
  ];

  it('provides complete configuration for all 9 FP8 states', () => {
    allStatuses.forEach((status) => {
      const config = getStatusConfig(status);
      expect(config).toBeDefined();
      expect(config.label).toBeTruthy();
      expect(config.description).toBeTruthy();
      expect(config.badgeClass).toBeTruthy();
      expect(config.dotClass).toBeTruthy();
      expect(config.iconName).toBeTruthy();
    });
  });

  it('correctly identifies terminal states', () => {
    const terminalStatuses: AgentStatus[] = [
      'completed',
      'failed',
      'cancelled',
      'timed_out',
      'expired',
    ];

    allStatuses.forEach((status) => {
      const expectedTerminal = terminalStatuses.includes(status);
      expect(isTerminalStatus(status)).toBe(expectedTerminal);
      expect(STATUS_CONFIGS[status].isTerminal).toBe(expectedTerminal);
    });
  });

  it('correctly identifies cancellable states', () => {
    const cancellableStatuses: AgentStatus[] = [
      'created',
      'planning',
      'running',
      'waiting_for_approval',
    ];

    allStatuses.forEach((status) => {
      const expectedCancellable = cancellableStatuses.includes(status);
      expect(isCancellableStatus(status)).toBe(expectedCancellable);
      expect(STATUS_CONFIGS[status].isCancellable).toBe(expectedCancellable);
    });
  });

  it('fallbacks safely on unknown or raw status', () => {
    const config = getStatusConfig('UNKNOWN_STATUS' as AgentStatus);
    expect(config.label).toBe('Created');
  });
});
