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
    <div className="relative w-full max-w-3xl mx-auto lg:max-w-none pt-2 pb-6">
      {/* Subtle warm champagne / gold ambient glow behind mockup */}
      <div className="absolute -inset-6 bg-radial from-[#e2caa6]/8 via-[#78b18a]/4 to-transparent blur-3xl -z-10 pointer-events-none" />

      {/* Main Perspective/Elevated Product Window matching Reference A & B */}
      <div
        className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)] shadow-[0_25px_60px_rgba(0,0,0,0.7)] overflow-hidden transition-all duration-500 hover:shadow-[0_30px_70px_rgba(0,0,0,0.85)]"
        style={{
          transform: 'perspective(1400px) rotateY(-3deg) rotateX(2deg)',
          transformStyle: 'preserve-3d',
        }}
      >
        {/* Mockup Top Command Bar */}
        <div className="h-11 border-b border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-4 flex items-center justify-between text-xs text-[var(--forge-text-muted)] font-mono">
          <div className="flex items-center gap-2.5">
            <span className="text-[var(--forge-text-secondary)] font-medium text-xs">
              acme-platform
            </span>
            <span className="text-[var(--forge-text-muted)]">/</span>
            <div className="flex items-center gap-1.5 text-[var(--forge-text-primary)] font-medium">
              <GitBranch className="h-3.5 w-3.5 text-[var(--forge-accent)]" />
              <span>main</span>
              <span className="text-[10px] text-[var(--forge-text-muted)]">▾</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded-full bg-[var(--forge-surface)] border border-[var(--forge-border)] flex items-center justify-center text-[10px] font-bold text-[var(--forge-accent)]">
              H
            </div>
          </div>
        </div>

        {/* Mockup Workspace Area (Mini Sidebar + Agent Card) */}
        <div className="flex min-h-[320px]">
          {/* Left Mini Icon Rail */}
          <div className="w-12 border-r border-[var(--forge-border)] bg-[var(--forge-surface)] py-3 px-2 flex flex-col items-center justify-between shrink-0">
            <div className="space-y-4 flex flex-col items-center">
              {/* Mini Forge Logo Symbol */}
              <div className="h-7 w-7 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-accent)] p-1">
                <ForgeLogoIcon size={16} />
              </div>
              <Home className="h-4 w-4 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors" />
              <FolderGit2 className="h-4 w-4 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors" />
              <CheckSquare className="h-4 w-4 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors" />
              <Code2 className="h-4 w-4 text-[var(--forge-accent)]" />
              <GitBranch className="h-4 w-4 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors" />
            </div>
            <Settings className="h-4 w-4 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors" />
          </div>

          {/* Main Agent Session Card Area */}
          <div className="flex-1 p-6 sm:p-7 bg-[var(--forge-surface)] flex flex-col justify-between">
            <div className="flex items-start justify-between gap-6">
              {/* Agent info */}
              <div className="space-y-2.5 max-w-lg">
                <div className="flex items-center gap-2 text-xs text-[var(--forge-text-muted)] font-mono">
                  <span className="h-2 w-2 rounded-full bg-[var(--forge-success)] animate-pulse" />
                  <span>Agent session</span>
                </div>

                <h3 className="text-lg sm:text-xl font-bold text-[var(--forge-text-primary)] tracking-tight leading-snug">
                  Refactor authentication flow
                </h3>

                <p className="text-xs sm:text-sm text-[var(--forge-text-secondary)] leading-relaxed">
                  Improve the authentication system by implementing OAuth2, refresh tokens, and role-based access control.
                </p>

                {/* Status Pills */}
                <div className="flex flex-wrap items-center gap-2.5 pt-2 text-xs font-mono">
                  <span className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)] px-2.5 py-1 font-semibold">
                    <Play className="h-2.5 w-2.5 fill-current" />
                    <span>Running</span>
                  </span>

                  <span className="inline-flex items-center gap-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] text-[var(--forge-text-secondary)] px-2.5 py-1">
                    <Bot className="h-3.5 w-3.5 text-[var(--forge-accent)]" />
                    <span>GPT-4o</span>
                  </span>

                  <span className="inline-flex items-center gap-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] px-2.5 py-1">
                    <Clock className="h-3.5 w-3.5" />
                    <span>23m 47s</span>
                  </span>
                </div>
              </div>

              {/* Glowing 3D Translucent Isometric Cube Visual */}
              <div className="hidden sm:flex shrink-0 items-center justify-center pr-2">
                <IsometricCube size={145} />
              </div>
            </div>

            {/* Progress Bar & Percentage */}
            <div className="pt-6 space-y-1.5">
              <div className="flex items-center justify-between text-xs font-mono">
                <div className="flex-1 h-2 rounded-full bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] overflow-hidden mr-3">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[var(--forge-success)] to-[var(--forge-champagne)] transition-all duration-1000"
                    style={{ width: '72%' }}
                  />
                </div>
                <span className="text-[var(--forge-text-primary)] font-bold text-xs">72%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4 Floating Metric Cards Overlapping the Mockup Window as in Reference A */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 -mt-5 relative z-20 px-2 sm:px-4">
        {/* Card 1: Files changed */}
        <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)]/95 backdrop-blur-md p-3.5 space-y-1.5 shadow-xl hover:border-[var(--forge-border-highlight)] transition-colors">
          <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
            <span>Files changed</span>
            <FileText className="h-4 w-4 text-[var(--forge-text-muted)]" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-lg sm:text-xl font-bold font-mono text-[var(--forge-text-primary)]">
              18
            </span>
            <div className="flex items-center gap-1 text-[11px] font-mono font-semibold">
              <span className="text-[var(--forge-success)]">+12</span>
              <span className="text-[var(--forge-danger)]">-6</span>
            </div>
          </div>
        </div>

        {/* Card 2: Lines changed */}
        <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)]/95 backdrop-blur-md p-3.5 space-y-1.5 shadow-xl hover:border-[var(--forge-border-highlight)] transition-colors">
          <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
            <span>Lines changed</span>
            <FileCode className="h-4 w-4 text-[var(--forge-text-muted)]" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-lg sm:text-xl font-bold font-mono text-[var(--forge-text-primary)]">
              842
            </span>
            <div className="flex items-center gap-1 text-[11px] font-mono font-semibold">
              <span className="text-[var(--forge-success)]">+612</span>
              <span className="text-[var(--forge-danger)]">-230</span>
            </div>
          </div>
        </div>

        {/* Card 3: Tools used */}
        <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)]/95 backdrop-blur-md p-3.5 space-y-1.5 shadow-xl hover:border-[var(--forge-border-highlight)] transition-colors">
          <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
            <span>Tools used</span>
            <Hash className="h-4 w-4 text-[var(--forge-text-muted)]" />
          </div>
          <div className="flex items-baseline gap-1.5 truncate">
            <span className="text-lg sm:text-xl font-bold font-mono text-[var(--forge-text-primary)]">
              7
            </span>
            <span className="text-[11px] text-[var(--forge-text-muted)] font-mono truncate">
              Read, Edit, Write...
            </span>
          </div>
        </div>

        {/* Card 4: Token usage */}
        <div className="rounded-xl border border-[var(--forge-border)] bg-[var(--forge-surface)]/95 backdrop-blur-md p-3.5 space-y-1.5 shadow-xl hover:border-[var(--forge-border-highlight)] transition-colors">
          <div className="flex items-center justify-between text-xs text-[var(--forge-text-muted)]">
            <span>Token usage</span>
            <Key className="h-4 w-4 text-[var(--forge-text-muted)]" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-lg sm:text-xl font-bold font-mono text-[var(--forge-text-primary)]">
              45.2k
            </span>
            <span className="inline-flex items-center text-[11px] font-mono font-semibold text-[var(--forge-success)]">
              <ArrowDown className="h-3 w-3" />
              <span>12%</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
