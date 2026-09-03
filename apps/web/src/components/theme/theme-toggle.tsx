'use client';

import { Moon, Sun } from 'lucide-react';
import React from 'react';
import { useTheme } from './theme-provider';

export interface ThemeToggleProps {
  readonly className?: string;
  readonly showLabel?: boolean;
}

export function ThemeToggle({
  className = '',
  showLabel = false,
}: ThemeToggleProps) {
  const { resolvedTheme, toggleTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`inline-flex items-center justify-center gap-2 rounded-md p-1.5 text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:bg-[var(--forge-surface-secondary)] border border-transparent hover:border-[var(--forge-border)] transition-colors focus:outline-hidden focus-visible:ring-1 focus-visible:ring-[var(--forge-accent)] ${className}`}
      aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
      title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
    >
      {isDark ? (
        <Sun className="h-4 w-4 shrink-0 text-[var(--forge-text-secondary)]" />
      ) : (
        <Moon className="h-4 w-4 shrink-0 text-[var(--forge-text-secondary)]" />
      )}
      {showLabel && (
        <span className="text-xs font-medium">
          {isDark ? 'Light' : 'Dark'} Mode
        </span>
      )}
    </button>
  );
}
