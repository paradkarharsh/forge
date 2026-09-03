import React from 'react';

interface ForgeLogoProps {
  readonly size?: 'sm' | 'md' | 'lg';
  readonly showTagline?: boolean;
  readonly className?: string;
}

export function ForgeLogo({
  size = 'md',
  showTagline = false,
  className = '',
}: ForgeLogoProps) {
  const iconSizes = {
    sm: 18,
    md: 22,
    lg: 28,
  };

  const textSizes = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-xl',
  };

  const iconDim = iconSizes[size];

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Minimalist Rounded-Bar F Vector Symbol matching canonical reference */}
      <svg
        width={iconDim}
        height={iconDim}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
        aria-hidden="true"
      >
        {/* Vertical rounded pillar */}
        <rect
          x="3.5"
          y="2.5"
          width="4.5"
          height="19"
          rx="2.25"
          fill="currentColor"
          className="text-[var(--forge-accent)]"
        />
        {/* Top horizontal rounded bar */}
        <rect
          x="8"
          y="2.5"
          width="12.5"
          height="4.5"
          rx="2.25"
          fill="currentColor"
          className="text-[var(--forge-accent)]"
        />
        {/* Middle horizontal rounded bar (slightly shorter) */}
        <rect
          x="8"
          y="9.5"
          width="9.5"
          height="4.5"
          rx="2.25"
          fill="currentColor"
          className="text-[var(--forge-accent)]"
        />
      </svg>

      {/* Geometric uppercase wordmark */}
      <div className="flex flex-col justify-center">
        <span
          className={`font-sans font-bold tracking-[0.14em] leading-none text-[var(--forge-text-primary)] ${textSizes[size]}`}
        >
          FORGE
        </span>
        {showTagline && (
          <span className="text-[9px] tracking-[0.2em] font-mono text-[var(--forge-text-muted)] uppercase mt-0.5 font-medium">
            BUILD BETTER. SHIP FASTER.
          </span>
        )}
      </div>
    </div>
  );
}
