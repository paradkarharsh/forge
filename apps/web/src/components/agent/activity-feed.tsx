'use client';

import {
  AlertCircle,
  ArrowDown,
  Code2,
  Filter,
  Layers,
  ListOrdered,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type {
  AgentEvent,
  AgentStep,
  AgentToolCall,
} from '../../lib/api/types';
import { LifecycleEventItem } from './lifecycle-event-item';
import { StepItem } from './step-item';
import { ToolCallItem } from './tool-call-item';

type ActivityFilter = 'all' | 'steps' | 'tools' | 'errors';

interface ActivityFeedProps {
  readonly steps: AgentStep[];
  readonly toolCalls: AgentToolCall[];
  readonly events: AgentEvent[];
}

interface FeedItem {
  readonly id: string;
  readonly type: 'step' | 'tool_call' | 'lifecycle';
  readonly timestamp: string;
  readonly data: AgentStep | AgentToolCall | AgentEvent;
}

export function ActivityFeed({
  steps,
  toolCalls,
  events,
}: ActivityFeedProps) {
  const [filter, setFilter] = useState<ActivityFilter>('all');
  const [userHasScrolledUp, setUserHasScrolledUp] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Combine and sort chronologically
  const feedItems = useMemo(() => {
    const items: FeedItem[] = [];

    steps.forEach((s) => {
      items.push({
        id: `step-${s.id}`,
        type: 'step',
        timestamp: s.created_at,
        data: s,
      });
    });

    toolCalls.forEach((tc) => {
      items.push({
        id: `tc-${tc.id}`,
        type: 'tool_call',
        timestamp: tc.created_at,
        data: tc,
      });
    });

    // Lifecycle milestones from events
    const significantEvents = events.filter((e) =>
      [
        'agent.created',
        'agent.planning_started',
        'agent.plan_created',
        'agent.running',
        'agent.approval_requested',
        'agent.approval_granted',
        'agent.approval_denied',
        'agent.completed',
        'agent.cancelled',
        'agent.failed',
      ].includes(e.event_type)
    );

    significantEvents.forEach((ev) => {
      items.push({
        id: `ev-${ev.id}`,
        type: 'lifecycle',
        timestamp: ev.timestamp,
        data: ev,
      });
    });

    // Sort ascending by creation time
    items.sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    return items;
  }, [steps, toolCalls, events]);

  // Apply filtering
  const filteredItems = useMemo(() => {
    switch (filter) {
      case 'steps':
        return feedItems.filter((item) => item.type === 'step');
      case 'tools':
        return feedItems.filter((item) => item.type === 'tool_call');
      case 'errors':
        return feedItems.filter((item) => {
          if (item.type === 'step') {
            return (item.data as AgentStep).status === 'failed';
          }
          if (item.type === 'tool_call') {
            const tc = item.data as AgentToolCall;
            return tc.status === 'failed' || tc.status === 'rejected' || Boolean(tc.error_message);
          }
          if (item.type === 'lifecycle') {
            return (item.data as AgentEvent).event_type === 'agent.failed';
          }
          return false;
        });
      case 'all':
      default:
        return feedItems;
    }
  }, [feedItems, filter]);

  // Handle scroll to track if user scrolled up
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setUserHasScrolledUp(!isAtBottom);
  };

  // Auto-scroll when new items arrive if user hasn't scrolled up
  useEffect(() => {
    if (!userHasScrolledUp) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [filteredItems.length, userHasScrolledUp]);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    setUserHasScrolledUp(false);
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950/40 rounded-xl border border-zinc-800/80 overflow-hidden">
      {/* Feed Control Bar */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 px-4 py-2.5 bg-zinc-900/30">
        <div className="flex items-center gap-1.5 text-xs text-zinc-400 font-medium">
          <Layers className="h-4 w-4 text-zinc-500" />
          <span>Execution Activity</span>
          <span className="ml-1 text-[11px] font-mono px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
            {filteredItems.length}
          </span>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
              filter === 'all'
                ? 'bg-zinc-800 text-zinc-100 shadow-xs'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setFilter('steps')}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${
              filter === 'steps'
                ? 'bg-zinc-800 text-zinc-100 shadow-xs'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <ListOrdered className="h-3 w-3" />
            <span>Steps</span>
          </button>
          <button
            type="button"
            onClick={() => setFilter('tools')}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${
              filter === 'tools'
                ? 'bg-zinc-800 text-zinc-100 shadow-xs'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Code2 className="h-3 w-3" />
            <span>Tools</span>
          </button>
          <button
            type="button"
            onClick={() => setFilter('errors')}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${
              filter === 'errors'
                ? 'bg-rose-950/50 text-rose-300 border border-rose-800/40'
                : 'text-zinc-400 hover:text-rose-300'
            }`}
          >
            <AlertCircle className="h-3 w-3" />
            <span>Errors</span>
          </button>
        </div>
      </div>

      {/* Main Timeline Scrollable Container */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-3"
      >
        {filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center text-zinc-500">
            <Filter className="h-8 w-8 mb-2 stroke-1 text-zinc-600" />
            <p className="text-sm font-medium text-zinc-400">No activity to show</p>
            <p className="text-xs text-zinc-600 mt-0.5">
              {filter !== 'all'
                ? `No events matching filter '${filter}'`
                : 'Waiting for agent to initialize steps...'}
            </p>
          </div>
        ) : (
          filteredItems.map((item) => {
            if (item.type === 'step') {
              return <StepItem key={item.id} step={item.data as AgentStep} />;
            }
            if (item.type === 'tool_call') {
              return (
                <ToolCallItem key={item.id} toolCall={item.data as AgentToolCall} />
              );
            }
            if (item.type === 'lifecycle') {
              return (
                <LifecycleEventItem
                  key={item.id}
                  event={item.data as AgentEvent}
                />
              );
            }
            return null;
          })
        )}
        <div ref={bottomRef} />
      </div>

      {/* Scroll to bottom floating button when scrolled up */}
      {userHasScrolledUp && (
        <div className="absolute bottom-4 right-6 z-10 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <button
            type="button"
            onClick={scrollToBottom}
            className="flex items-center gap-1.5 rounded-full bg-indigo-600 hover:bg-indigo-700 px-3 py-1.5 text-xs font-medium text-white shadow-lg transition-colors"
          >
            <ArrowDown className="h-3.5 w-3.5" />
            <span>Scroll to latest</span>
          </button>
        </div>
      )}
    </div>
  );
}
