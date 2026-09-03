import React from 'react';

export interface ForgeLogoProps {
  readonly size?: 'sm' | 'md' | 'lg' | 'xl';
  readonly showWordmark?: boolean;
  readonly showTagline?: boolean;
  readonly className?: string;
}

const sizeMap = {
  sm: { icon: 20, text: 'text-sm font-bold tracking-tight', gap: 'gap-2' },
  md: { icon: 26, text: 'text-base font-bold tracking-tight', gap: 'gap-2.5' },
  lg: { icon: 34, text: 'text-xl font-extrabold tracking-tight', gap: 'gap-3' },
  xl: { icon: 44, text: 'text-2xl font-extrabold tracking-tight', gap: 'gap-3.5' },
} as const;

/**
 * The Canonical Forge Vector Logo Symbol
 *
 * Precisely mapped to the approved Forge Logo reference:
 * - Top piece: Horizontal capsule bar with rounded semicircle endcaps.
 * - Bottom piece: Inverted L/hook stem with rounded outer corner, horizontal arm,
 *   smooth inner fillet transition, and semicircular bottom terminal cap.
 */
export function ForgeLogoIcon({ size = 26, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      viewBox="230 200 560 600"
      width={size}
      height={size}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className}`}
      aria-hidden="true"
    >
      {/* Top horizontal capsule bar */}
      <rect
        x="266"
        y="229"
        width="496"
        height="137"
        rx="68.5"
        fill="currentColor"
      />
      {/* Bottom hook / stem with smooth fillet and semicircular bottom */}
      <path
        d="M 343 436 L 590 436 A 26 26 0 0 1 616 462 L 616 502 C 616 540 585 574 546 574 L 440 574 C 423 574 410 587 410 604 L 410 704 A 72 72 0 0 1 266 704 L 266 513 A 77 77 0 0 1 343 436 Z"
        fill="currentColor"
      />
    </svg>
  );
}

/**
 * Forge Brand Component: Symbol + Wordmark + Optional Tagline
 */
export function ForgeLogo({
  size = 'md',
  showWordmark = true,
  showTagline = false,
  className = '',
}: ForgeLogoProps) {
  const config = sizeMap[size];

  return (
    <div className={`inline-flex items-center ${config.gap} text-[var(--forge-text-primary)] select-none ${className}`}>
      <ForgeLogoIcon size={config.icon} className="text-[var(--forge-accent)]" />

      {showWordmark && (
        <div className="flex flex-col justify-center">
          <span className={`font-sans uppercase text-[var(--forge-text-primary)] leading-none ${config.text}`}>
            FORGE
          </span>
          {showTagline && (
            <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-[var(--forge-text-muted)] mt-1 font-medium">
              BUILD BETTER. SHIP FASTER.
            </span>
          )}
        </div>
      )}
    </div>
  );
}
