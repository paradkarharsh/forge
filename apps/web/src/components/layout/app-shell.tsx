'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Bell,
  Bot,
  Box,
  ChevronsLeft,
  ChevronDown,
  FolderGit2,
  GitBranch,
  GitPullRequest,
  Home,
  Menu,
  Search,
  Settings,
  Terminal,
  X,
} from 'lucide-react';
import { ForgeLogo } from '../brand/forge-logo';
import { ThemeToggle } from '../theme/theme-toggle';

export interface AppShellProps {
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
  readonly children: React.ReactNode;
  readonly activeAgentCount?: number;
}

export function AppShell({
  workspaceId,
  repositoryId,
  children,
}: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navItems = [
    {
      label: 'Overview',
      href: `/workspaces/${workspaceId}`,
      icon: Home,
      active: pathname === `/workspaces/${workspaceId}`,
    },
    {
      label: 'Repositories',
      href: `/workspaces/${workspaceId}/repositories`,
      icon: FolderGit2,
      active: pathname.includes('/repositories') && !pathname.includes('/agents'),
    },
    {
      label: 'Pull requests',
      href: `/workspaces/${workspaceId}/pull-requests`,
      icon: GitPullRequest,
      active: pathname.includes('/pull-requests'),
    },
    {
      label: 'Agents',
      href: `/workspaces/${workspaceId}/agents`,
      icon: Bot,
      active: pathname.includes('/agents'),
    },
    {
      label: 'Sessions',
      href: `/workspaces/${workspaceId}/agents`,
      icon: Terminal,
      active: false,
    },
    {
      label: 'Environments',
      href: `/workspaces/${workspaceId}/environments`,
      icon: Box,
      active: pathname.includes('/environments'),
    },
    {
      label: 'Settings',
      href: `/workspaces/${workspaceId}/settings`,
      icon: Settings,
      active: pathname.includes('/settings'),
    },
  ];

  return (
    <div className="flex h-screen w-full bg-[var(--forge-bg)] text-[var(--forge-text-primary)] overflow-hidden font-sans">
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/70 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ------------------------------------------------ */}
      {/* LEFT SIDEBAR (Matching forge-agent-reference.png) */}
      {/* ------------------------------------------------ */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-[var(--forge-surface)] border-r border-[var(--forge-border)] flex flex-col justify-between transition-transform duration-200 lg:static lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col flex-1 min-h-0 overflow-y-auto">
          {/* Top Header: Logo + Collapse Button */}
          <div className="h-14 border-b border-[var(--forge-border)] px-4 flex items-center justify-between shrink-0">
            <Link href="/" className="hover:opacity-90 transition-opacity">
              <ForgeLogo size="sm" showTagline={false} />
            </Link>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="hidden lg:flex p-1 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors"
                title="Collapse sidebar"
              >
                <ChevronsLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="lg:hidden p-1 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Project Selector Box: [FC] forge-core ▾ */}
          <div className="p-3 border-b border-[var(--forge-border-subtle)]">
            <div className="flex items-center justify-between rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2.5 py-1.5 text-xs text-[var(--forge-text-primary)] cursor-pointer hover:border-[var(--forge-border-highlight)] transition-colors">
              <div className="flex items-center gap-2 truncate">
                <span className="h-5 w-5 rounded bg-[var(--forge-surface)] border border-[var(--forge-border)] flex items-center justify-center font-mono text-[9px] font-bold text-[var(--forge-text-muted)] shrink-0">
                  FC
                </span>
                <span className="font-medium truncate font-mono text-xs">
                  {repositoryId || 'forge-core'}
                </span>
              </div>
              <ChevronDown className="h-3.5 w-3.5 text-[var(--forge-text-muted)] shrink-0" />
            </div>
          </div>

          {/* Main Navigation List */}
          <nav className="p-2 space-y-0.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                    item.active
                      ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)] shadow-2xs font-semibold'
                      : 'text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:bg-[var(--forge-surface-secondary)]/60'
                  }`}
                >
                  <Icon className="h-4 w-4 text-[var(--forge-text-muted)] shrink-0" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* ACTIVE AGENTS Section */}
          <div className="px-3 pt-3 pb-1 border-t border-[var(--forge-border-subtle)] space-y-2">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-[var(--forge-text-muted)] font-semibold">
              <span>ACTIVE AGENTS</span>
            </div>

            <div className="space-y-1">
              {/* Agent 1 */}
              <Link
                href={`/workspaces/${workspaceId}/agents`}
                className="flex items-center justify-between p-1.5 rounded hover:bg-[var(--forge-surface-secondary)] transition-colors text-xs"
              >
                <div className="flex items-center gap-2 truncate">
                  <div className="h-6 w-6 rounded bg-[var(--forge-success-surface)] border border-[var(--forge-success-border)] flex items-center justify-center text-[var(--forge-success)] shrink-0">
                    <Bot className="h-3.5 w-3.5" />
                  </div>
                  <div className="truncate">
                    <p className="text-[11px] font-medium text-[var(--forge-text-primary)] truncate">
                      Refactor auth flow
                    </p>
                    <p className="text-[10px] text-[var(--forge-success)] font-mono">
                      Running
                    </p>
                  </div>
                </div>
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--forge-success)] shrink-0 animate-pulse ml-1" />
              </Link>

              {/* Agent 2 */}
              <Link
                href={`/workspaces/${workspaceId}/agents`}
                className="flex items-center justify-between p-1.5 rounded hover:bg-[var(--forge-surface-secondary)] transition-colors text-xs"
              >
                <div className="flex items-center gap-2 truncate">
                  <div className="h-6 w-6 rounded bg-[var(--forge-warning-surface)] border border-[var(--forge-warning-border)] flex items-center justify-center text-[var(--forge-warning)] shrink-0">
                    <Bot className="h-3.5 w-3.5" />
                  </div>
                  <div className="truncate">
                    <p className="text-[11px] font-medium text-[var(--forge-text-primary)] truncate">
                      Add rate limiting
                    </p>
                    <p className="text-[10px] text-[var(--forge-warning)] font-mono">
                      Waiting approval
                    </p>
                  </div>
                </div>
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--forge-warning)] shrink-0 ml-1" />
              </Link>

              {/* Agent 3 */}
              <Link
                href={`/workspaces/${workspaceId}/agents`}
                className="flex items-center justify-between p-1.5 rounded hover:bg-[var(--forge-surface-secondary)] transition-colors text-xs"
              >
                <div className="flex items-center gap-2 truncate">
                  <div className="h-6 w-6 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center text-[var(--forge-text-muted)] shrink-0">
                    <Bot className="h-3.5 w-3.5" />
                  </div>
                  <div className="truncate">
                    <p className="text-[11px] font-medium text-[var(--forge-text-primary)] truncate">
                      Fix flaky tests
                    </p>
                    <p className="text-[10px] text-[var(--forge-text-muted)] font-mono">
                      Queued
                    </p>
                  </div>
                </div>
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--forge-text-muted)] shrink-0 ml-1" />
              </Link>
            </div>

            <Link
              href={`/workspaces/${workspaceId}/agents`}
              className="inline-block text-[10px] font-mono text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors pt-1"
            >
              View all agents →
            </Link>
          </div>

          {/* Forge Pro Card */}
          <div className="p-3 mt-auto">
            <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-3 space-y-2">
              <p className="text-xs font-semibold text-[var(--forge-text-primary)]">
                Forge Pro
              </p>
              <p className="text-[11px] text-[var(--forge-text-secondary)] leading-relaxed">
                Unlock concurrent agents, higher limits, and advanced security.
              </p>
              <button
                type="button"
                className="w-full rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] hover:border-[var(--forge-border-highlight)] py-1 text-xs font-medium text-[var(--forge-text-primary)] transition-colors"
              >
                Upgrade now
              </button>
            </div>
          </div>
        </div>

        {/* User Footer matching reference */}
        <div className="p-3 border-t border-[var(--forge-border)] flex items-center justify-between bg-[var(--forge-surface)] shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-7 w-7 rounded-full bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center font-bold text-xs text-[var(--forge-accent)] shrink-0">
              H
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1">
                <p className="text-xs font-semibold text-[var(--forge-text-primary)] truncate">Harsh</p>
                <ChevronDown className="h-3 w-3 text-[var(--forge-text-muted)] shrink-0" />
              </div>
              <p className="text-[10px] text-[var(--forge-text-muted)] font-mono truncate">harsh@forge.dev</p>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </aside>

      {/* ------------------------------------------------ */}
      {/* MAIN VIEW AREA + TOP BAR */}
      {/* ------------------------------------------------ */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navigation Bar matching reference */}
        <header className="h-12 border-b border-[var(--forge-border)] bg-[var(--forge-surface)] px-4 flex items-center justify-between shrink-0 text-xs">
          {/* Left: Breadcrumbs / Repo / Branch dropdowns */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-1 text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)]"
            >
              <Menu className="h-4 w-4" />
            </button>

            <div className="flex items-center gap-2 font-mono text-[11px] text-[var(--forge-text-muted)]">
              <span>Workspace</span>
              <span>/</span>
              <div className="flex items-center gap-1 text-[var(--forge-text-primary)] cursor-pointer hover:text-[var(--forge-accent)]">
                <span>{repositoryId || 'forge-core'}</span>
                <span className="text-[9px]">▾</span>
              </div>
              <span>/</span>
              <div className="flex items-center gap-1 text-[var(--forge-text-primary)] cursor-pointer hover:text-[var(--forge-accent)]">
                <GitBranch className="h-3 w-3 text-[var(--forge-accent)]" />
                <span>main</span>
                <span className="text-[9px]">▾</span>
              </div>
            </div>
          </div>

          {/* Right: Search, Notifications, Profile */}
          <div className="flex items-center gap-3">
            {/* Search Input Box */}
            <div className="hidden sm:flex items-center gap-2 bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] rounded px-2.5 py-1 text-xs text-[var(--forge-text-muted)] font-mono w-56">
              <Search className="h-3.5 w-3.5" />
              <span className="flex-1 text-[11px]">Search anything...</span>
              <kbd className="bg-[var(--forge-surface)] border border-[var(--forge-border)] rounded px-1 py-0.2 text-[9px]">
                ⌘K
              </kbd>
            </div>

            {/* Notification Bell with Dot */}
            <button
              type="button"
              className="relative p-1.5 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)] transition-colors"
            >
              <Bell className="h-4 w-4" />
              <span className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-[var(--forge-warning)]" />
            </button>

            {/* User Profile */}
            <div className="flex items-center gap-1.5 cursor-pointer pl-1">
              <div className="h-6 w-6 rounded-full bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center font-bold text-[10px] text-[var(--forge-accent)]">
                H
              </div>
              <span className="text-xs font-medium text-[var(--forge-text-primary)] hidden md:inline">Harsh</span>
              <ChevronDown className="h-3 w-3 text-[var(--forge-text-muted)] hidden md:inline" />
            </div>
          </div>
        </header>

        {/* Content Body */}
        <main className="flex-1 overflow-y-auto bg-[var(--forge-bg)]">
          {children}
        </main>
      </div>
    </div>
  );
}
