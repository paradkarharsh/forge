import { describe, expect, it } from 'vitest';
import { getStatusConfig } from '../lib/utils/status';

describe('Canonical Visual System & Design Tokens', () => {
  it('enforces restrained status color palette matching design specifications', () => {
    const runningConfig = getStatusConfig('running');
    expect(runningConfig.badgeClass).toContain('--forge-success');
    expect(runningConfig.dotClass).toContain('--forge-success');

    const waitingConfig = getStatusConfig('waiting_for_approval');
    expect(waitingConfig.badgeClass).toContain('--forge-warning');
    expect(waitingConfig.dotClass).toContain('--forge-warning');

    const completedConfig = getStatusConfig('completed');
    expect(completedConfig.badgeClass).toContain('--forge-success');
    expect(completedConfig.dotClass).toContain('--forge-success');

    const failedConfig = getStatusConfig('failed');
    expect(failedConfig.badgeClass).toContain('--forge-danger');
    expect(failedConfig.dotClass).toContain('--forge-danger');

    const planningConfig = getStatusConfig('planning');
    expect(planningConfig.badgeClass).toContain('--forge-accent');
    expect(planningConfig.dotClass).toContain('--forge-accent');
  });

  it('prohibits forbidden colors (blue, indigo, purple, neon) in status tokens', () => {
    const allStatuses = [
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

    for (const status of allStatuses) {
      const config = getStatusConfig(status);
      expect(config.badgeClass).not.toContain('blue');
      expect(config.badgeClass).not.toContain('indigo');
      expect(config.badgeClass).not.toContain('purple');
      expect(config.badgeClass).not.toContain('violet');
      expect(config.dotClass).not.toContain('blue');
      expect(config.dotClass).not.toContain('indigo');
    }
  });
});
