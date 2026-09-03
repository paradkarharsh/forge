'use client';

import {
  AlertCircle,
  Bot,
  Plus,
  RefreshCw,
  Search,
} from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { AgentSession } from '../../lib/api/types';
import { AgentCard } from './agent-card';

type FilterTab = 'all' | 'active' | 'waiting' | 'completed' | 'failed';

interface AgentListProps {
  readonly sessions: AgentSession[];
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
  readonly isLoading: boolean;
  readonly error: Error | null;
  readonly onRefresh: () => void;
}

export function AgentList({
  sessions,
  workspaceId,
  repositoryId,
  isLoading,
  error,
  onRefresh,
}: AgentListProps) {
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const newAgentHref = repositoryId
    ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents/new`
    : `/workspaces/${workspaceId}/agents/new`;

  // Filter sessions
  const filteredSessions = useMemo(() => {
    return sessions.filter((s) => {
      // Tab filter
      if (activeTab === 'active') {
        if (s.status !== 'planning' && s.status !== 'running' && s.status !== 'created') {
          return false;
        }
      } else if (activeTab === 'waiting') {
        if (s.status !== 'waiting_for_approval') {
          return false;
        }
      } else if (activeTab === 'completed') {
        if (s.status !== 'completed') {
          return false;
        }
      } else if (activeTab === 'failed') {
        if (s.status !== 'failed' && s.status !== 'cancelled' && s.status !== 'timed_out' && s.status !== 'expired') {
          return false;
        }
      }

      // Search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        return (
          s.objective.toLowerCase().includes(query) ||
          s.id.toLowerCase().includes(query) ||
          (s.model && s.model.toLowerCase().includes(query))
        );
      }

      return true;
    });
  }, [sessions, activeTab, searchQuery]);

  return (
    <div className="space-y-4">
      {/* Header Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by task or ID..."
              className="w-full rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] pl-8 pr-3 py-1 text-xs text-[var(--forge-text-primary)] placeholder-[var(--forge-text-muted)] focus:border-[var(--forge-accent)] focus:outline-hidden transition-colors"
            />
          </div>

          <button
            type="button"
            onClick={onRefresh}
            title="Refresh agents"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:border-[var(--forge-border-highlight)] transition-colors"
          >
            <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Create Agent Action */}
        <Link
          href={newAgentHref}
          className="inline-flex items-center justify-center gap-1.5 rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-3.5 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors shrink-0"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New Agent</span>
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-[var(--forge-border)] text-xs overflow-x-auto pb-px">
        {[
          { id: 'all', label: 'All Agents', count: sessions.length },
          {
            id: 'active',
            label: 'Active',
            count: sessions.filter((s) => ['created', 'planning', 'running'].includes(s.status)).length,
          },
          {
            id: 'waiting',
            label: 'Waiting for Approval',
            count: sessions.filter((s) => s.status === 'waiting_for_approval').length,
          },
          {
            id: 'completed',
            label: 'Completed',
            count: sessions.filter((s) => s.status === 'completed').length,
          },
          {
            id: 'failed',
            label: 'Failed & Stopped',
            count: sessions.filter((s) => ['failed', 'cancelled', 'timed_out', 'expired'].includes(s.status)).length,
          },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id as FilterTab)}
            className={`flex items-center gap-1.5 px-3 py-1.5 border-b-2 font-medium transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? 'border-[var(--forge-accent)] text-[var(--forge-text-primary)]'
                : 'border-transparent text-[var(--forge-text-muted)] hover:text-[var(--forge-text-secondary)]'
            }`}
          >
            <span>{tab.label}</span>
            <span
              className={`rounded-full px-1.5 py-0.2 text-[10px] font-mono border ${
                activeTab === tab.id
                  ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] border-[var(--forge-border)]'
                  : 'bg-[var(--forge-surface)] text-[var(--forge-text-muted)] border-[var(--forge-border-subtle)]'
              }`}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Loading Skeletons */}
      {isLoading && sessions.length === 0 && (
        <div className="space-y-2.5">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded border border-[var(--forge-danger-border)] bg-[var(--forge-danger-surface)] p-4 text-center space-y-2">
          <AlertCircle className="h-5 w-5 text-[var(--forge-danger)] mx-auto" />
          <div className="space-y-0.5">
            <h4 className="text-xs font-semibold text-[var(--forge-danger)]">
              Failed to load agents
            </h4>
            <p className="text-[11px] text-[var(--forge-danger)] font-mono">
              {error.message}
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded border border-[var(--forge-danger-border)] bg-[var(--forge-surface)] px-2.5 py-1 text-xs font-medium text-[var(--forge-text-primary)] hover:border-[var(--forge-border-highlight)] transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && filteredSessions.length === 0 && (
        <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-8 text-center space-y-3">
          <div className="flex h-10 w-10 mx-auto items-center justify-center rounded bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] border border-[var(--forge-border)]">
            <Bot className="h-5 w-5" />
          </div>
          <div className="space-y-1 max-w-sm mx-auto">
            <h3 className="text-xs font-semibold text-[var(--forge-text-primary)]">
              {searchQuery || activeTab !== 'all' ? 'No matching agents' : 'No agents yet'}
            </h3>
            <p className="text-xs text-[var(--forge-text-muted)] leading-relaxed">
              {searchQuery || activeTab !== 'all'
                ? 'Try adjusting your search criteria or switching filter tabs.'
                : 'Formulate an objective to inspect symbols, modify code, and execute tools.'}
            </p>
          </div>
          {(!searchQuery && activeTab === 'all') && (
            <Link
              href={newAgentHref}
              className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-accent)] hover:bg-[var(--forge-accent-hover)] px-3.5 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] shadow-xs transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Create First Agent</span>
            </Link>
          )}
        </div>
      )}

      {/* Cards List */}
      {!isLoading && !error && filteredSessions.length > 0 && (
        <div className="space-y-2">
          {filteredSessions.map((session) => (
            <AgentCard
              key={session.id}
              session={session}
              workspaceId={workspaceId}
              repositoryId={repositoryId}
            />
          ))}
        </div>
      )}
    </div>
  );
}
