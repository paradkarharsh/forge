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
          <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-1.5 py-0.2 rounded bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border border-[var(--forge-danger-border)]">
            <Shield className="h-2.5 w-2.5" />
            <span>Critical</span>
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-1.5 py-0.2 rounded bg-[var(--forge-warning-surface)] text-[var(--forge-warning)] border border-[var(--forge-warning-border)]">
            <Shield className="h-2.5 w-2.5" />
            <span>High</span>
          </span>
        );
      case 'low':
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-1.5 py-0.2 rounded bg-[var(--forge-surface-secondary)] text-[var(--forge-text-muted)] border border-[var(--forge-border)]">
            <span>Low</span>
          </span>
        );
    }
  };

  const getToolIcon = () => {
    if (toolCall.tool_name.startsWith('terminal.')) {
      return <Terminal className="h-3.5 w-3.5 text-[var(--forge-success)]" />;
    }
    if (toolCall.tool_name.startsWith('file.')) {
      return <Code2 className="h-3.5 w-3.5 text-[var(--forge-accent)]" />;
    }
    return <Wrench className="h-3.5 w-3.5 text-[var(--forge-text-secondary)]" />;
  };

  const getStatusIcon = () => {
    switch (toolCall.status) {
      case 'completed':
        return <CheckCircle2 className="h-3.5 w-3.5 text-[var(--forge-success)]" />;
      case 'failed':
      case 'rejected':
        return <AlertCircle className="h-3.5 w-3.5 text-[var(--forge-danger)]" />;
      case 'running':
      case 'pending':
      default:
        return <Clock className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />;
    }
  };

  return (
    <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] transition-colors hover:border-[var(--forge-border-highlight)] overflow-hidden">
      {/* Clickable Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between gap-3 p-3 text-left focus:outline-hidden"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-[var(--forge-surface-secondary)] border border-[var(--forge-border-subtle)]">
            {getToolIcon()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold text-[var(--forge-text-primary)] truncate">
                {toolCall.tool_name}
              </span>
              {getRiskBadge(toolCall.risk_level)}
            </div>
            {toolCall.duration_ms != null && (
              <span className="text-[10px] font-mono text-[var(--forge-text-muted)]">
                {toolCall.duration_ms}ms
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <div className="flex items-center gap-1 text-[11px] font-mono text-[var(--forge-text-secondary)]">
            {getStatusIcon()}
            <span className="capitalize">{toolCall.status}</span>
          </div>
          <span className="text-[10px] font-mono text-[var(--forge-text-muted)] hidden sm:inline">
            {formatRelativeTime(toolCall.created_at)}
          </span>
          <div className="text-[var(--forge-text-muted)]">
            {isExpanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </div>
        </div>
      </button>

      {/* Expandable Details Area */}
      {isExpanded && (
        <div className="border-t border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-3 space-y-2.5 text-xs">
          {/* Arguments */}
          <div>
            <div className="text-[10px] font-medium text-[var(--forge-text-muted)] uppercase tracking-wider mb-1">
              Arguments
            </div>
            <pre className="font-mono text-[11px] leading-relaxed text-[var(--forge-text-secondary)] bg-[var(--forge-surface)] border border-[var(--forge-border)] rounded p-2 overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>

          {/* Output */}
          {toolCall.output && (
            <div>
              <div className="flex items-center justify-between text-[10px] font-medium text-[var(--forge-text-muted)] uppercase tracking-wider mb-1">
                <span>Output</span>
                <span className="text-[10px] text-[var(--forge-text-muted)] font-normal lowercase">
                  (untrusted external data)
                </span>
              </div>
              <pre className="font-mono text-[11px] leading-relaxed text-[var(--forge-text-primary)] bg-[var(--forge-surface)] border border-[var(--forge-border)] rounded p-2 overflow-x-auto max-h-60">
                {toolCall.output}
              </pre>
            </div>
          )}

          {/* Error Message */}
          {toolCall.error_message && (
            <div>
              <div className="text-[10px] font-medium text-[var(--forge-danger)] uppercase tracking-wider mb-1">
                Error
              </div>
              <div className="font-mono text-[11px] text-[var(--forge-danger)] bg-[var(--forge-danger-surface)] border border-[var(--forge-danger-border)] rounded p-2">
                {toolCall.error_message}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
