'use client';

import {
  Check,
  Coins,
  Copy,
  Cpu,
  Gauge,
  Info,
  ShieldAlert,
} from 'lucide-react';
import { useState } from 'react';
import type { AgentApproval, AgentSession } from '../../lib/api/types';
import {
  formatCost,
  formatDateTime,
  formatDuration,
  formatTokens,
} from '../../lib/utils/formatters';

interface SessionSidebarProps {
  readonly session: AgentSession;
  readonly approvals: AgentApproval[];
}

export function SessionSidebar({ session, approvals }: SessionSidebarProps) {
  const [copied, setCopied] = useState(false);

  const copyId = () => {
    navigator.clipboard.writeText(session.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const pendingApproval = approvals.find((a) => a.status === 'pending');

  const totalTokens =
    session.metrics.total_input_tokens + session.metrics.total_output_tokens;

  return (
    <aside className="w-full lg:w-72 shrink-0 space-y-3.5 text-[var(--forge-text-primary)]">
      {/* Human Approval Alert (When in WAITING_FOR_APPROVAL) */}
      {session.status === 'waiting_for_approval' && pendingApproval && (
        <div className="rounded-lg border border-[var(--forge-warning-border)] bg-[var(--forge-warning-surface)] p-3.5 space-y-2">
          <div className="flex items-center gap-1.5 text-[var(--forge-warning)] font-semibold text-xs uppercase tracking-wider">
            <ShieldAlert className="h-4 w-4" />
            <span>Approval Required</span>
          </div>
          <p className="text-xs text-[var(--forge-text-secondary)] leading-relaxed">
            The agent requested execution of high-risk tool{' '}
            <code className="font-mono text-[var(--forge-text-primary)] font-medium bg-[var(--forge-surface)] px-1 py-0.5 rounded border border-[var(--forge-border)]">
              {pendingApproval.tool_name}
            </code>
            . Execution is suspended on the worker.
          </p>
          <div className="text-[11px] font-mono text-[var(--forge-warning)] pt-0.5">
            ID: {pendingApproval.id.slice(0, 8)}…
          </div>
        </div>
      )}

      {/* Failure Reason Banner (If status is failed) */}
      {session.status === 'failed' && session.failure_reason && (
        <div className="rounded-lg border border-[var(--forge-danger-border)] bg-[var(--forge-danger-surface)] p-3.5 space-y-1 text-xs">
          <span className="font-semibold text-[var(--forge-danger)] uppercase tracking-wider text-[10px]">
            Failure Reason
          </span>
          <p className="text-[var(--forge-danger)] font-mono text-xs leading-relaxed">
            {session.failure_reason}
          </p>
        </div>
      )}

      {/* Execution Usage & Cost Card */}
      <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--forge-text-primary)]">
            <Coins className="h-4 w-4 text-[var(--forge-text-muted)]" />
            <span>Usage & Cost</span>
          </div>
          <span className="font-mono text-xs font-bold text-[var(--forge-success)]">
            {formatCost(session.metrics.estimated_cost_usd)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded border border-[var(--forge-border-subtle)] bg-[var(--forge-surface-secondary)] p-2">
            <span className="text-[10px] uppercase font-mono text-[var(--forge-text-muted)] block mb-0.5">
              LLM Calls
            </span>
            <div className="flex items-baseline gap-1 font-mono">
              <span className="text-sm font-semibold text-[var(--forge-text-primary)]">
                {session.metrics.total_llm_calls}
              </span>
              <span className="text-[var(--forge-text-muted)] text-[10px]">
                / {session.limits.max_llm_calls}
              </span>
            </div>
            {session.metrics.total_llm_retries > 0 && (
              <span className="text-[10px] text-[var(--forge-warning)] font-mono block mt-0.5">
                {session.metrics.total_llm_retries} retries
              </span>
            )}
          </div>

          <div className="rounded border border-[var(--forge-border-subtle)] bg-[var(--forge-surface-secondary)] p-2">
            <span className="text-[10px] uppercase font-mono text-[var(--forge-text-muted)] block mb-0.5">
              Tool Calls
            </span>
            <div className="flex items-baseline gap-1 font-mono">
              <span className="text-sm font-semibold text-[var(--forge-text-primary)]">
                {session.metrics.total_tool_calls}
              </span>
              <span className="text-[var(--forge-text-muted)] text-[10px]">
                / {session.limits.max_tool_calls}
              </span>
            </div>
          </div>
        </div>

        <div className="space-y-1.5 pt-1 text-xs border-t border-[var(--forge-border-subtle)]">
          <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
            <span>Input Tokens</span>
            <span className="font-mono text-[var(--forge-text-primary)]">
              {formatTokens(session.metrics.total_input_tokens)}
            </span>
          </div>
          <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
            <span>Output Tokens</span>
            <span className="font-mono text-[var(--forge-text-primary)]">
              {formatTokens(session.metrics.total_output_tokens)}
            </span>
          </div>
          <div className="flex items-center justify-between text-[var(--forge-text-primary)] font-medium pt-1 border-t border-[var(--forge-border-subtle)]">
            <span>Total Tokens</span>
            <span className="font-mono text-[var(--forge-text-primary)]">
              {formatTokens(totalTokens)}
            </span>
          </div>
        </div>
      </div>

      {/* Durable Execution Limits */}
      <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--forge-text-primary)]">
          <Gauge className="h-4 w-4 text-[var(--forge-text-muted)]" />
          <span>Execution Limits</span>
        </div>

        <div className="space-y-1.5 text-xs">
          <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
            <span>Max Wall Time</span>
            <span className="font-mono text-[var(--forge-text-primary)]">
              {formatDuration(session.limits.max_wall_time_seconds)}
            </span>
          </div>
          <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
            <span>Max Output</span>
            <span className="font-mono text-[var(--forge-text-primary)]">
              {(session.limits.max_output_bytes / 1024).toFixed(0)} KB
            </span>
          </div>
          <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
            <span>Max Observation</span>
            <span className="font-mono text-[var(--forge-text-primary)]">
              {(session.limits.max_observation_bytes / 1024).toFixed(0)} KB
            </span>
          </div>
        </div>
      </div>

      {/* Session Metadata Card */}
      <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--forge-text-primary)]">
          <Info className="h-4 w-4 text-[var(--forge-text-muted)]" />
          <span>Session Details</span>
        </div>

        <div className="space-y-2 text-xs">
          <div>
            <span className="text-[10px] font-mono text-[var(--forge-text-muted)] uppercase block mb-1">
              Session ID
            </span>
            <button
              type="button"
              onClick={copyId}
              className="w-full flex items-center justify-between gap-2 rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border)] px-2 py-1 font-mono text-[11px] text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] hover:border-[var(--forge-border-highlight)] transition-colors"
            >
              <span className="truncate">{session.id}</span>
              {copied ? (
                <Check className="h-3 w-3 text-[var(--forge-success)] shrink-0" />
              ) : (
                <Copy className="h-3 w-3 text-[var(--forge-text-muted)] shrink-0" />
              )}
            </button>
          </div>

          {session.model && (
            <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
              <span className="inline-flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
                <span>Model</span>
              </span>
              <span className="font-mono text-[var(--forge-text-primary)] font-medium">
                {session.model}
              </span>
            </div>
          )}

          <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
            <span>Created</span>
            <span className="font-mono text-[var(--forge-text-primary)]">
              {formatDateTime(session.created_at)}
            </span>
          </div>

          {session.started_at && (
            <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
              <span>Started</span>
              <span className="font-mono text-[var(--forge-text-primary)]">
                {formatDateTime(session.started_at)}
              </span>
            </div>
          )}

          {session.completed_at && (
            <div className="flex items-center justify-between text-[var(--forge-text-secondary)]">
              <span>Completed</span>
              <span className="font-mono text-[var(--forge-text-primary)]">
                {formatDateTime(session.completed_at)}
              </span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
