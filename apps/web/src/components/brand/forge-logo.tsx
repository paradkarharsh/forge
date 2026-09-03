import React from 'react';

export interface ForgeLogoProps {
  readonly size?: 'sm' | 'md' | 'lg';
  readonly showWordmark?: boolean;
  readonly showTagline?: boolean;
  readonly className?: string;
  readonly emblemClassName?: string;
}

export function ForgeLogo({
  size = 'md',
  showWordmark = true,
  showTagline = false,
  className = '',
  emblemClassName = '',
}: ForgeLogoProps) {
  const dimensions = {
    sm: { box: 'h-6 w-6', text: 'text-sm', tag: 'text-[8px]' },
    md: { box: 'h-8 w-8', text: 'text-base', tag: 'text-[9px]' },
    lg: { box: 'h-10 w-10', text: 'text-xl', tag: 'text-[10px]' },
  }[size];

  return (
    <div className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      {/* Minimal rounded-bar "F" emblem */}
      <svg
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`${dimensions.box} shrink-0 text-[var(--forge-accent)] ${emblemClassName}`}
        aria-label="Forge Logo"
      >
        {/* Vertical rounded pillar */}
        <rect x="4" y="3.5" width="4.5" height="17" rx="2.25" fill="currentColor" />
        {/* Top horizontal crossbar */}
        <rect x="8.5" y="3.5" width="11.5" height="4.5" rx="2.25" fill="currentColor" />
        {/* Middle horizontal crossbar */}
        <rect x="8.5" y="10.25" width="8" height="4" rx="2" fill="currentColor" />
      </svg>

      {/* Wordmark and Tagline */}
      {showWordmark && (
        <div className="flex flex-col">
          <span
            className={`font-semibold tracking-[0.18em] uppercase text-[var(--forge-text-primary)] leading-none ${dimensions.text}`}
          >
            FORGE
          </span>
          {showTagline && (
            <span
              className={`font-mono uppercase tracking-[0.24em] text-[var(--forge-text-muted)] mt-1 ${dimensions.tag}`}
            >
              BUILD BETTER. SHIP FASTER.
            </span>
          )}
        </div>
      )}
    </div>
  );
}
