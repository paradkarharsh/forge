'use client';

import React from 'react';
import {
  ArrowDown,
  Bot,
  CheckSquare,
  Clock,
  Code2,
  FileCode,
  FileText,
  FolderGit2,
  GitBranch,
  Hash,
  Home,
  Key,
  Play,
  Settings,
} from 'lucide-react';
import { ForgeLogoIcon } from '../brand/forge-logo';
import { IsometricCube } from '../brand/isometric-cube';

export function HeroProductMockup() {
  return (
    <div className="relative w-full max-w-2xl mx-auto lg:max-w-none">
      {/* Subtle warm champagne / gold ambient glow behind mockup */}
      <div className="absolute -inset-4 bg-radial from-[#E5A952]/10 via-[#78B18A]/5 to-transparent blur-2xl -z-10 pointer-events-none" />

      {/* Main Perspective/Elevated Mockup Window */}
      <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden transition-transform duration-500 hover:scale-[1.01]">
        {/* Mockup Top Command Bar */}
        <div className="h-10 border-b border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-3.5 flex items-center justify-between text-xs text-[var(--forge-text-muted)] font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[var(--forge-text-secondary)] font-medium">acme-platform</span>
            <span>/</span>
            <div className="flex items-center gap-1 text-[var(--forge-text-primary)]">
              <GitBranch className="h-3 w-3 text-[var(--forge-accent)]" />
              <span>main</span>
              <span className="text-[10px]">▾</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="h-5 w-5 rounded-full bg-[var(--forge-surface)] border border-[var(--forge-border)] flex items-center justify-center text-[9px] font-bold text-[var(--forge-accent)]">
              H
            </div>
          </div>
        </div>

        {/* Mockup Workspace Area (Mini Sidebar + Agent Card) */}
        <div className="flex min-h-[280px]">
          {/* Left Mini Icon Rail */}
          <div className="w-11 border-r border-[var(--forge-border)] bg-[var(--forge-surface)] p-2 flex flex-col items-center justify-between shrink-0">
            <div className="space-y-3 flex flex-col items-center">
              {/* Mini Forge Logo */}
              <div className="h-6 w-6 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-accent)] p-0.5">
                <ForgeLogoIcon size={14} />
              </div>
              <Home className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
              <FolderGit2 className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
              <CheckSquare className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
              <Code2 className="h-3.5 w-3.5 text-[var(--forge-accent)]" />
              <GitBranch className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
            </div>
            <Settings className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          </div>

          {/* Main Agent Session Card Area */}
          <div className="flex-1 p-5 bg-[var(--forge-surface)] flex flex-col justify-between">
            <div className="flex items-start justify-between gap-4">
              {/* Agent info */}
              <div className="space-y-2 max-w-md">
                <div className="flex items-center gap-1.5 text-xs text-[var(--forge-text-muted)] font-mono">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--forge-success)] animate-pulse" />
                  <span>Agent session</span>
                </div>

                <h3 className="text-base sm:text-lg font-bold text-[var(--forge-text-primary)] tracking-tight leading-snug">
                  Refactor authentication flow
                </h3>

                <p className="text-xs text-[var(--forge-text-secondary)] leading-relaxed">
                  Improve the authentication system by implementing OAuth2, refresh tokens, and role-based access control.
                </p>

                {/* Status Pills */}
                <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] font-mono">
                  <span className="inline-flex items-center gap-1 rounded bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)] px-2 py-0.5 font-semibold">
                    <Play className="h-2.5 w-2.5 fill-current" />
                    <span>Running</span>
                  </span>

                  <span className="inline-flex items-center gap-1 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] text-[var(--forge-text-secondary)] px-2 py-0.5">
                    <Bot className="h-3 w-3 text-[var(--forge-accent)]" />
                    <span>GPT-4o</span>
                  </span>

                  <span className="inline-flex items-center gap-1 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] px-2 py-0.5">
                    <Clock className="h-3 w-3" />
                    <span>23m 47s</span>
                  </span>
                </div>
              </div>

              {/* Glowing 3D Isometric Cube Visual */}
              <div className="hidden sm:flex shrink-0">
                <IsometricCube size={120} />
              </div>
            </div>

            {/* Progress Bar & Percentage */}
            <div className="pt-4 space-y-1">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <div className="flex-1 h-1.5 rounded-full bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] overflow-hidden mr-3">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[var(--forge-success)] to-[var(--forge-accent)] transition-all duration-1000"
                    style={{ width: '72%' }}
                  />
                </div>
                <span className="text-[var(--forge-text-primary)] font-bold text-xs">72%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4 Floating Metric Cards Below Mockup matching Reference */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-3">
        {/* Card 1: Files changed */}
        <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)]/95 backdrop-blur-sm p-3 space-y-1 shadow-md">
          <div className="flex items-center justify-between text-[11px] text-[var(--forge-text-muted)]">
            <span>Files changed</span>
            <FileText className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-base sm:text-lg font-bold font-mono text-[var(--forge-text-primary)]">
              18
            </span>
            <div className="flex items-center gap-1 text-[10px] font-mono font-semibold">
              <span className="text-[var(--forge-success)]">+12</span>
              <span className="text-[var(--forge-danger)]">-6</span>
            </div>
          </div>
        </div>

        {/* Card 2: Lines changed */}
        <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)]/95 backdrop-blur-sm p-3 space-y-1 shadow-md">
          <div className="flex items-center justify-between text-[11px] text-[var(--forge-text-muted)]">
            <span>Lines changed</span>
            <FileCode className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-base sm:text-lg font-bold font-mono text-[var(--forge-text-primary)]">
              842
            </span>
            <div className="flex items-center gap-1 text-[10px] font-mono font-semibold">
              <span className="text-[var(--forge-success)]">+612</span>
              <span className="text-[var(--forge-danger)]">-230</span>
            </div>
          </div>
        </div>

        {/* Card 3: Tools used */}
        <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)]/95 backdrop-blur-sm p-3 space-y-1 shadow-md">
          <div className="flex items-center justify-between text-[11px] text-[var(--forge-text-muted)]">
            <span>Tools used</span>
            <Hash className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          </div>
          <div className="flex items-baseline gap-1.5 truncate">
            <span className="text-base sm:text-lg font-bold font-mono text-[var(--forge-text-primary)]">
              7
            </span>
            <span className="text-[10px] text-[var(--forge-text-muted)] font-mono truncate">
              Read, Edit, Write...
            </span>
          </div>
        </div>

        {/* Card 4: Token usage */}
        <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)]/95 backdrop-blur-sm p-3 space-y-1 shadow-md">
          <div className="flex items-center justify-between text-[11px] text-[var(--forge-text-muted)]">
            <span>Token usage</span>
            <Key className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-base sm:text-lg font-bold font-mono text-[var(--forge-text-primary)]">
              45.2k
            </span>
            <span className="inline-flex items-center text-[10px] font-mono font-semibold text-[var(--forge-success)]">
              <ArrowDown className="h-2.5 w-2.5" />
              <span>12%</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
