'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Bot,
  Brain,
  ChevronDown,
  FolderGit2,
  LayoutDashboard,
  Menu,
  Plus,
  Search,
  Settings,
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
  activeAgentCount,
}: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const agentsHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents`
    : `/workspaces/${workspaceId}/agents`;

  const newAgentHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents/new`
    : `/workspaces/${workspaceId}/agents/new`;

  const navItems = [
    {
      label: 'Dashboard',
      href: `/workspaces/${workspaceId}`,
      icon: LayoutDashboard,
      active: pathname === `/workspaces/${workspaceId}`,
    },
    {
      label: 'Agents',
      href: agentsHref,
      icon: Bot,
      active: pathname.includes('/agents'),
      badge: activeAgentCount && activeAgentCount > 0 ? activeAgentCount : undefined,
    },
    {
      label: 'Repositories',
      href: `/workspaces/${workspaceId}/repositories`,
      icon: FolderGit2,
      active: pathname.includes('/repositories') && !pathname.includes('/agents'),
    },
    {
      label: 'Memory',
      href: `/workspaces/${workspaceId}/memory`,
      icon: Brain,
      active: pathname.includes('/memory'),
    },
    {
      label: 'Settings',
      href: `/workspaces/${workspaceId}/settings`,
      icon: Settings,
      active: pathname.includes('/settings'),
    },
  ];

  return (
    <div className="flex h-screen w-full bg-[var(--forge-bg)] text-[var(--forge-text-primary)] overflow-hidden">
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-60 bg-[var(--forge-surface)] border-r border-[var(--forge-border)] flex flex-col justify-between transition-transform duration-200 lg:static lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col">
          {/* Logo & Close */}
          <div className="h-14 border-b border-[var(--forge-border)] px-4 flex items-center justify-between">
            <Link href="/" className="hover:opacity-90 transition-opacity">
              <ForgeLogo size="sm" />
            </Link>
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="lg:hidden p-1 text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Workspace Switcher */}
          <div className="p-3 border-b border-[var(--forge-border-subtle)]">
            <div className="flex items-center justify-between rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2.5 py-1.5 text-xs text-[var(--forge-text-primary)]">
              <div className="flex items-center gap-2 truncate">
                <span className="h-2 w-2 rounded-full bg-[var(--forge-success)] shrink-0" />
                <span className="font-medium truncate font-mono text-[11px]">
                  ws-{workspaceId.slice(0, 8)}
                </span>
              </div>
              <ChevronDown className="h-3 w-3 text-[var(--forge-text-muted)] shrink-0" />
            </div>
          </div>

          {/* Nav Items */}
          <nav className="p-2 space-y-0.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center justify-between px-2.5 py-1.5 rounded text-xs font-medium transition-colors ${
                    item.active
                      ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border border-[var(--forge-border)]'
                      : 'text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:bg-[var(--forge-surface-secondary)]'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="h-4 w-4 text-[var(--forge-text-muted)]" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="rounded-full bg-[var(--forge-success-surface)] text-[var(--forge-success)] border border-[var(--forge-success-border)] px-1.5 py-0.2 text-[10px] font-mono font-semibold">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* User Profile & Theme Toggle */}
        <div className="p-3 border-t border-[var(--forge-border)] flex items-center justify-between bg-[var(--forge-surface)]">
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-6 w-6 rounded-full bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] flex items-center justify-center font-mono text-[10px] font-bold text-[var(--forge-accent)] shrink-0">
              E
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-[var(--forge-text-primary)] truncate">Engineer</p>
              <p className="text-[10px] text-[var(--forge-text-muted)] font-mono">dev@forge.local</p>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </aside>

      {/* Main Column */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Command Bar */}
        <header className="h-12 border-b border-[var(--forge-border)] bg-[var(--forge-surface)] px-4 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-1 text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)]"
            >
              <Menu className="h-4 w-4" />
            </button>

            {/* Quiet context / breadcrumbs */}
            <div className="flex items-center gap-2 text-xs text-[var(--forge-text-muted)] font-mono">
              <span>forge</span>
              <span>/</span>
              <span className="text-[var(--forge-text-primary)] font-medium">
                {pathname.includes('/agents/new')
                  ? 'new-agent'
                  : pathname.includes('/agents/')
                  ? 'agent-session'
                  : pathname.includes('/agents')
                  ? 'agents'
                  : pathname.includes('/repositories')
                  ? 'repositories'
                  : pathname.includes('/memory')
                  ? 'memory'
                  : 'workspace'}
              </span>
            </div>
          </div>

          {/* Right Action Items */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-[var(--forge-text-muted)] font-mono bg-[var(--forge-surface-secondary)] px-2 py-1 rounded border border-[var(--forge-border)]">
              <Search className="h-3 w-3" />
              <span>⌘K</span>
            </div>

            <div className="h-4 w-px bg-[var(--forge-border)] hidden sm:block" />

            <div className="flex items-center gap-1.5 text-[11px] text-[var(--forge-success)] font-mono">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--forge-success)] animate-pulse" />
              <span className="hidden md:inline">Gateway Online</span>
            </div>

            <Link
              href={newAgentHref}
              className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-2.5 py-1 text-xs font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">New Agent</span>
            </Link>
          </div>
        </header>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto bg-[var(--forge-bg)]">
          {children}
        </main>
      </div>
    </div>
  );
}
