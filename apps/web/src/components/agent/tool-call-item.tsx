'use client';

import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Code2,
  Shield,
  Terminal,
  Wrench,
} from 'lucide-react';
import { useState } from 'react';
import type { AgentToolCall, ToolRiskLevel } from '../../lib/api/types';
import { formatRelativeTime } from '../../lib/utils/formatters';

interface ToolCallItemProps {
  readonly toolCall: AgentToolCall;
}

export function ToolCallItem({ toolCall }: ToolCallItemProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getRiskBadge = (risk: ToolRiskLevel) => {
    switch (risk) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
            <Shield className="h-2.5 w-2.5" />
            <span>Critical</span>
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <Shield className="h-2.5 w-2.5" />
            <span>High</span>
          </span>
        );
      case 'low':
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
            <span>Low</span>
          </span>
        );
    }
  };

  const getToolIcon = () => {
    if (toolCall.tool_name.startsWith('terminal.')) {
      return <Terminal className="h-4 w-4 text-emerald-400" />;
    }
    if (toolCall.tool_name.startsWith('file.')) {
      return <Code2 className="h-4 w-4 text-blue-400" />;
    }
    return <Wrench className="h-4 w-4 text-indigo-400" />;
  };

  const getStatusIcon = () => {
    switch (toolCall.status) {
      case 'completed':
        return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />;
      case 'failed':
      case 'rejected':
        return <AlertCircle className="h-3.5 w-3.5 text-rose-400" />;
      case 'running':
      case 'pending':
      default:
        return <Clock className="h-3.5 w-3.5 text-zinc-400" />;
    }
  };

  return (
    <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/30 transition-colors hover:border-zinc-700/80 overflow-hidden">
      {/* Clickable Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between gap-3 p-3 text-left focus:outline-hidden"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-zinc-800/70 border border-zinc-700/50">
            {getToolIcon()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold text-zinc-200 truncate">
                {toolCall.tool_name}
              </span>
              {getRiskBadge(toolCall.risk_level)}
            </div>
            {toolCall.duration_ms != null && (
              <span className="text-[11px] font-mono text-zinc-500">
                {toolCall.duration_ms}ms
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <div className="flex items-center gap-1 text-[11px] font-mono text-zinc-400">
            {getStatusIcon()}
            <span className="capitalize">{toolCall.status}</span>
          </div>
          <span className="text-[11px] font-mono text-zinc-500 hidden sm:inline">
            {formatRelativeTime(toolCall.created_at)}
          </span>
          <div className="text-zinc-500">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </div>
        </div>
      </button>

      {/* Expandable Details Area */}
      {isExpanded && (
        <div className="border-t border-zinc-800/80 bg-zinc-950/60 p-3.5 space-y-3 text-xs">
          {/* Arguments */}
          <div>
            <div className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-1.5">
              Arguments
            </div>
            <pre className="font-mono text-[11px] leading-relaxed text-zinc-300 bg-zinc-900 border border-zinc-800 rounded-md p-2.5 overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>

          {/* Output (External Untrusted Data Display) */}
          {toolCall.output && (
            <div>
              <div className="flex items-center justify-between text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-1.5">
                <span>Output</span>
                <span className="text-[10px] text-zinc-500 font-normal lowercase">
                  (external untrusted output)
                </span>
              </div>
              <pre className="font-mono text-[11px] leading-relaxed text-zinc-200 bg-black/60 border border-zinc-800/90 rounded-md p-2.5 overflow-x-auto max-h-60">
                {toolCall.output}
              </pre>
            </div>
          )}

          {/* Error Message */}
          {toolCall.error_message && (
            <div>
              <div className="text-[11px] font-medium text-rose-400 uppercase tracking-wider mb-1.5">
                Error
              </div>
              <div className="font-mono text-[11px] text-rose-300 bg-rose-950/30 border border-rose-500/30 rounded-md p-2.5">
                {toolCall.error_message}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
