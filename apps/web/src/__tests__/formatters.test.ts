import { describe, expect, it } from 'vitest';
import {
  formatCost,
  formatDuration,
  formatTokens,
  truncateText,
} from '../lib/utils/formatters';

describe('Formatters', () => {
  describe('formatDuration', () => {
    it('formats seconds correctly', () => {
      expect(formatDuration(0)).toBe('0s');
      expect(formatDuration(45)).toBe('45s');
      expect(formatDuration(60)).toBe('1m');
      expect(formatDuration(90)).toBe('1m 30s');
      expect(formatDuration(3600)).toBe('1h');
      expect(formatDuration(3665)).toBe('1h 1m');
      expect(formatDuration(null)).toBe('0s');
    });
  });

  describe('formatTokens', () => {
    it('formats token counts with k/M suffixes', () => {
      expect(formatTokens(0)).toBe('0');
      expect(formatTokens(850)).toBe('850');
      expect(formatTokens(1500)).toBe('1.5k');
      expect(formatTokens(2450000)).toBe('2.45M');
      expect(formatTokens(undefined)).toBe('0');
    });
  });

  describe('formatCost', () => {
    it('formats USD currency correctly', () => {
      expect(formatCost(0)).toBe('$0.00');
      expect(formatCost(0.0005)).toBe('<$0.01');
      expect(formatCost(0.1234)).toBe('$0.1234');
      expect(formatCost(15.5)).toBe('$15.5000');
      expect(formatCost(null)).toBe('$0.00');
    });
  });

  describe('truncateText', () => {
    it('truncates text over maxLength with ellipsis', () => {
      expect(truncateText('short', 10)).toBe('short');
      expect(truncateText('hello world text', 8)).toBe('hello wo…');
      expect(truncateText('', 10)).toBe('');
    });
  });
});
