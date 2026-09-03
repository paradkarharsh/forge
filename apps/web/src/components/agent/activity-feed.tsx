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
        id: `tool-${tc.id}`,
        type: 'tool_call',
        timestamp: tc.created_at,
        data: tc,
      });
    });

    events.forEach((ev) => {
      // Omit noisy internal pings from main feed
      if (ev.event_type !== 'agent.stream_ping') {
        items.push({
          id: `event-${ev.id}`,
          type: 'lifecycle',
          timestamp: ev.timestamp,
          data: ev,
        });
      }
    });

    return items.sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }, [steps, toolCalls, events]);

  const filteredItems = useMemo(() => {
    if (filter === 'steps') {
      return feedItems.filter((i) => i.type === 'step');
    }
    if (filter === 'tools') {
      return feedItems.filter((i) => i.type === 'tool_call');
    }
    if (filter === 'errors') {
      return feedItems.filter((i) => {
        if (i.type === 'step') {
          return (i.data as AgentStep).status === 'failed';
        }
        if (i.type === 'tool_call') {
          const tc = i.data as AgentToolCall;
          return tc.status === 'failed' || tc.status === 'rejected';
        }
        if (i.type === 'lifecycle') {
          return (i.data as AgentEvent).event_type.includes('fail');
        }
        return false;
      });
    }
    return feedItems;
  }, [feedItems, filter]);

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
    <div className="relative flex flex-col h-full bg-[var(--forge-surface)] rounded-lg border border-[var(--forge-border)] overflow-hidden">
      {/* Feed Control Bar */}
      <div className="flex items-center justify-between border-b border-[var(--forge-border)] px-4 py-2 bg-[var(--forge-surface-secondary)]">
        <div className="flex items-center gap-1.5 text-xs text-[var(--forge-text-secondary)] font-medium">
          <Layers className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          <span>Execution Activity</span>
          <span className="ml-1 text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-[var(--forge-surface)] text-[var(--forge-text-muted)] border border-[var(--forge-border-subtle)]">
            {filteredItems.length}
          </span>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 bg-[var(--forge-surface)] border border-[var(--forge-border)] rounded p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              filter === 'all'
                ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] shadow-xs'
                : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
            }`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setFilter('steps')}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              filter === 'steps'
                ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] shadow-xs'
                : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
            }`}
          >
            <ListOrdered className="h-3 w-3" />
            <span>Steps</span>
          </button>
          <button
            type="button"
            onClick={() => setFilter('tools')}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              filter === 'tools'
                ? 'bg-[var(--forge-surface-secondary)] text-[var(--forge-text-primary)] shadow-xs'
                : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-text-primary)]'
            }`}
          >
            <Code2 className="h-3 w-3" />
            <span>Tools</span>
          </button>
          <button
            type="button"
            onClick={() => setFilter('errors')}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              filter === 'errors'
                ? 'bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border border-[var(--forge-danger-border)]'
                : 'text-[var(--forge-text-muted)] hover:text-[var(--forge-danger)]'
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
        className="flex-1 overflow-y-auto p-4 space-y-2.5"
      >
        {filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center text-[var(--forge-text-muted)]">
            <Filter className="h-7 w-7 mb-2 stroke-1 text-[var(--forge-text-muted)]" />
            <p className="text-xs font-medium text-[var(--forge-text-secondary)]">No activity to show</p>
            <p className="text-[11px] text-[var(--forge-text-muted)] mt-0.5">
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
        <div className="absolute bottom-4 right-6 z-10">
          <button
            type="button"
            onClick={scrollToBottom}
            className="flex items-center gap-1.5 rounded-full bg-[var(--forge-accent)] text-[var(--forge-accent-foreground)] hover:bg-[var(--forge-accent-hover)] px-3 py-1.5 text-xs font-semibold shadow-md transition-colors"
          >
            <ArrowDown className="h-3.5 w-3.5" />
            <span>Scroll to latest</span>
          </button>
        </div>
      )}
    </div>
  );
}
