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
    <div className="space-y-6">
      {/* Header Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="relative flex-1 sm:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search agents by task or ID..."
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 pl-9 pr-3.5 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:border-indigo-500 focus:outline-hidden transition-colors"
            />
          </div>

          <button
            type="button"
            onClick={onRefresh}
            title="Refresh agents"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Create Agent Action */}
        <Link
          href={newAgentHref}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors shrink-0"
        >
          <Plus className="h-4 w-4" />
          <span>New Agent</span>
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-zinc-800 text-xs overflow-x-auto pb-px">
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
            className={`flex items-center gap-2 px-3 py-2 border-b-2 font-medium transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? 'border-indigo-500 text-zinc-100'
                : 'border-transparent text-zinc-400 hover:text-zinc-300'
            }`}
          >
            <span>{tab.label}</span>
            <span
              className={`rounded-full px-1.5 py-0.2 text-[10px] font-mono ${
                activeTab === tab.id
                  ? 'bg-indigo-500/20 text-indigo-300'
                  : 'bg-zinc-800 text-zinc-500'
              }`}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Loading Skeletons */}
      {isLoading && sessions.length === 0 && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 rounded-xl border border-zinc-800/80 bg-zinc-900/30 animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-5 text-center space-y-3">
          <AlertCircle className="h-6 w-6 text-rose-400 mx-auto" />
          <div className="space-y-1">
            <h4 className="text-sm font-semibold text-rose-300">
              Failed to load agents
            </h4>
            <p className="text-xs text-rose-200/80 font-mono">
              {error.message}
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-lg border border-rose-500/40 bg-rose-500/20 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-500/30 transition-colors"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && filteredSessions.length === 0 && (
        <div className="rounded-2xl border border-dashed border-zinc-800 bg-zinc-950/40 p-10 text-center space-y-4">
          <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Bot className="h-6 w-6" />
          </div>
          <div className="space-y-1.5 max-w-sm mx-auto">
            <h3 className="text-base font-semibold text-zinc-200">
              {searchQuery || activeTab !== 'all' ? 'No matching agents' : 'No agents yet'}
            </h3>
            <p className="text-xs text-zinc-500 leading-relaxed">
              {searchQuery || activeTab !== 'all'
                ? 'Try adjusting your search criteria or switching filter tabs.'
                : 'Start an AI agent to execute tasks, inspect code, modify files, and run tests.'}
            </p>
          </div>
          {(!searchQuery && activeTab === 'all') && (
            <Link
              href={newAgentHref}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>Create Your First Agent</span>
            </Link>
          )}
        </div>
      )}

      {/* Cards List */}
      {!isLoading && !error && filteredSessions.length > 0 && (
        <div className="space-y-3">
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
