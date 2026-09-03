/**
 * Display formatting utilities for timestamps, tokens, duration, and metrics.
 */

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds) || seconds < 0) {
    return '0s';
  }

  const s = Math.floor(seconds);
  if (s < 60) {
    return `${s}s`;
  }
  const m = Math.floor(s / 60);
  const remS = s % 60;
  if (m < 60) {
    return remS > 0 ? `${m}m ${remS}s` : `${m}m`;
  }
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return remM > 0 ? `${h}h ${remM}m` : `${h}h`;
}

export function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) {
    return '—';
  }

  const date = new Date(isoString);
  const now = new Date();
  const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffSec < 5) {
    return 'just now';
  }
  if (diffSec < 60) {
    return `${diffSec}s ago`;
  }
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) {
    return `${diffMin}m ago`;
  }
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return `${diffDays}d ago`;
  }

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) {
    return '—';
  }
  const date = new Date(isoString);
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatTokens(count: number | null | undefined): string {
  if (count == null || isNaN(count)) {
    return '0';
  }
  if (count < 1000) {
    return count.toLocaleString();
  }
  if (count < 1000000) {
    return `${(count / 1000).toFixed(1)}k`;
  }
  return `${(count / 1000000).toFixed(2)}M`;
}

export function formatCost(amountUsd: number | null | undefined): string {
  if (amountUsd == null || isNaN(amountUsd)) {
    return '$0.00';
  }
  if (amountUsd === 0) {
    return '$0.00';
  }
  if (amountUsd < 0.01) {
    return `<$0.01`;
  }
  return `$${amountUsd.toFixed(4)}`;
}

export function truncateText(text: string, maxLength = 100): string {
  if (!text) {
    return '';
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}…`;
}
