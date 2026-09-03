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
    <aside className="w-full lg:w-80 shrink-0 space-y-4 text-zinc-100">
      {/* Human Approval Alert (When in WAITING_FOR_APPROVAL) */}
      {session.status === 'waiting_for_approval' && pendingApproval && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 space-y-2">
          <div className="flex items-center gap-2 text-amber-400 font-semibold text-xs uppercase tracking-wider">
            <ShieldAlert className="h-4 w-4" />
            <span>Human Approval Required</span>
          </div>
          <p className="text-xs text-amber-200/90 leading-relaxed">
            The agent requested execution of high-risk tool{' '}
            <code className="font-mono text-amber-100 font-medium bg-amber-950/60 px-1 py-0.5 rounded">
              {pendingApproval.tool_name}
            </code>
            . Execution is safely suspended on the worker until decision.
          </p>
          <div className="text-[11px] font-mono text-amber-400/80 pt-1">
            Approval ID: {pendingApproval.id.slice(0, 8)}…
          </div>
        </div>
      )}

      {/* Failure Reason Banner (If status is failed) */}
      {session.status === 'failed' && session.failure_reason && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 space-y-1 text-xs">
          <span className="font-semibold text-rose-400 uppercase tracking-wider text-[11px]">
            Failure Reason
          </span>
          <p className="text-rose-200 font-mono text-xs leading-relaxed">
            {session.failure_reason}
          </p>
        </div>
      )}

      {/* Execution Usage & Cost Card */}
      <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 p-4 space-y-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
            <Coins className="h-4 w-4 text-emerald-400" />
            <span>Usage & Accounting</span>
          </div>
          <span className="font-mono text-xs font-bold text-emerald-400">
            {formatCost(session.metrics.estimated_cost_usd)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg border border-zinc-800/60 bg-zinc-900/40 p-2.5">
            <span className="text-[10px] uppercase font-mono text-zinc-400 block mb-0.5">
              LLM Calls
            </span>
            <div className="flex items-baseline gap-1 font-mono">
              <span className="text-sm font-semibold text-zinc-100">
                {session.metrics.total_llm_calls}
              </span>
              <span className="text-zinc-500 text-[11px]">
                / {session.limits.max_llm_calls}
              </span>
            </div>
            {session.metrics.total_llm_retries > 0 && (
              <span className="text-[10px] text-amber-400 font-mono block mt-0.5">
                {session.metrics.total_llm_retries} retries
              </span>
            )}
          </div>

          <div className="rounded-lg border border-zinc-800/60 bg-zinc-900/40 p-2.5">
            <span className="text-[10px] uppercase font-mono text-zinc-400 block mb-0.5">
              Tool Calls
            </span>
            <div className="flex items-baseline gap-1 font-mono">
              <span className="text-sm font-semibold text-zinc-100">
                {session.metrics.total_tool_calls}
              </span>
              <span className="text-zinc-500 text-[11px]">
                / {session.limits.max_tool_calls}
              </span>
            </div>
          </div>
        </div>

        <div className="space-y-1.5 pt-1 text-xs border-t border-zinc-800/60">
          <div className="flex items-center justify-between text-zinc-400">
            <span>Input Tokens</span>
            <span className="font-mono text-zinc-200">
              {formatTokens(session.metrics.total_input_tokens)}
            </span>
          </div>
          <div className="flex items-center justify-between text-zinc-400">
            <span>Output Tokens</span>
            <span className="font-mono text-zinc-200">
              {formatTokens(session.metrics.total_output_tokens)}
            </span>
          </div>
          <div className="flex items-center justify-between text-zinc-300 font-medium pt-1 border-t border-zinc-800/40">
            <span>Total Tokens</span>
            <span className="font-mono text-zinc-100">
              {formatTokens(totalTokens)}
            </span>
          </div>
        </div>
      </div>

      {/* Durable Execution Limits */}
      <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 p-4 space-y-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
          <Gauge className="h-4 w-4 text-indigo-400" />
          <span>Execution Limits</span>
        </div>

        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between text-zinc-400">
            <span>Max Wall Time</span>
            <span className="font-mono text-zinc-200">
              {formatDuration(session.limits.max_wall_time_seconds)}
            </span>
          </div>
          <div className="flex items-center justify-between text-zinc-400">
            <span>Max Output</span>
            <span className="font-mono text-zinc-200">
              {(session.limits.max_output_bytes / 1024).toFixed(0)} KB
            </span>
          </div>
          <div className="flex items-center justify-between text-zinc-400">
            <span>Max Observation</span>
            <span className="font-mono text-zinc-200">
              {(session.limits.max_observation_bytes / 1024).toFixed(0)} KB
            </span>
          </div>
        </div>
      </div>

      {/* Session Metadata Card */}
      <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 p-4 space-y-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
          <Info className="h-4 w-4 text-zinc-400" />
          <span>Session Details</span>
        </div>

        <div className="space-y-2.5 text-xs">
          <div>
            <span className="text-[10px] font-mono text-zinc-500 uppercase block mb-1">
              Session ID
            </span>
            <button
              type="button"
              onClick={copyId}
              className="w-full flex items-center justify-between gap-2 rounded-md bg-zinc-900 border border-zinc-800 px-2.5 py-1.5 font-mono text-[11px] text-zinc-300 hover:text-zinc-100 hover:border-zinc-700 transition-colors"
            >
              <span className="truncate">{session.id}</span>
              {copied ? (
                <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              ) : (
                <Copy className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
              )}
            </button>
          </div>

          {session.model && (
            <div className="flex items-center justify-between text-zinc-400">
              <span className="inline-flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-zinc-500" />
                <span>Model</span>
              </span>
              <span className="font-mono text-zinc-200 font-medium">
                {session.model}
              </span>
            </div>
          )}

          <div className="flex items-center justify-between text-zinc-400">
            <span>Created</span>
            <span className="font-mono text-zinc-300">
              {formatDateTime(session.created_at)}
            </span>
          </div>

          {session.started_at && (
            <div className="flex items-center justify-between text-zinc-400">
              <span>Started</span>
              <span className="font-mono text-zinc-300">
                {formatDateTime(session.started_at)}
              </span>
            </div>
          )}

          {session.completed_at && (
            <div className="flex items-center justify-between text-zinc-400">
              <span>Completed</span>
              <span className="font-mono text-zinc-300">
                {formatDateTime(session.completed_at)}
              </span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
