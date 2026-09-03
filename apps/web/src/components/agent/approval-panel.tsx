'use client';

import React, { useState } from 'react';
import { AlertTriangle, Check, X, Clock, ShieldAlert, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import type { AgentApproval, AgentToolCall } from '../../lib/api/types';

interface ApprovalPanelProps {
  readonly approval: AgentApproval;
  readonly toolCall?: AgentToolCall | null;
  readonly onApprove: (approvalId: string, reason?: string) => Promise<void>;
  readonly onDeny: (approvalId: string, reason?: string) => Promise<void>;
}

export function ApprovalPanel({
  approval,
  toolCall,
  onApprove,
  onDeny,
}: ApprovalPanelProps) {
  const [reason, setReason] = useState('');
  const [showDetails, setShowDetails] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionType, setActionType] = useState<'approve' | 'deny' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const riskLevel = (toolCall?.risk_level || (approval.metadata?.risk_level as string) || 'high').toUpperCase();

  const handleApprove = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setActionType('approve');
    setError(null);
    try {
      await onApprove(approval.id, reason.trim() || undefined);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to approve request';
      setError(msg);
      setIsSubmitting(false);
      setActionType(null);
    }
  };

  const handleDeny = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setActionType('deny');
    setError(null);
    try {
      await onDeny(approval.id, reason.trim() || undefined);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to deny request';
      setError(msg);
      setIsSubmitting(false);
      setActionType(null);
    }
  };

  const argsToDisplay = toolCall?.arguments || (approval.metadata?.arguments as Record<string, unknown>) || {};
  const targetPath = (argsToDisplay.path as string) || (argsToDisplay.command as string);

  return (
    <div
      role="region"
      aria-label="Action Approval Request"
      className="mb-6 rounded-lg border border-[var(--forge-warning-border)] bg-[var(--forge-surface)] p-5 shadow-xs"
    >
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start space-x-3.5">
          <div className="rounded-md bg-[var(--forge-warning-surface)] p-2 text-[var(--forge-warning)] border border-[var(--forge-warning-border)]">
            <ShieldAlert className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center space-x-2.5">
              <h3 className="text-sm font-semibold text-[var(--forge-text-primary)]">
                Human Approval Required
              </h3>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium uppercase tracking-wider ${
                  riskLevel === 'CRITICAL'
                    ? 'bg-[var(--forge-danger-surface)] text-[var(--forge-danger)] border border-[var(--forge-danger-border)]'
                    : 'bg-[var(--forge-warning-surface)] text-[var(--forge-warning)] border border-[var(--forge-warning-border)]'
                }`}
              >
                {riskLevel} Risk
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--forge-text-secondary)]">
              This action requires explicit authorization before execution proceeds.
            </p>
          </div>
        </div>

        {approval.expires_at && (
          <div className="flex items-center space-x-1.5 text-xs text-[var(--forge-text-muted)] bg-[var(--forge-surface-secondary)] px-2.5 py-1 rounded border border-[var(--forge-border)] self-start">
            <Clock className="h-3.5 w-3.5" />
            <span>Expires: {new Date(approval.expires_at).toLocaleTimeString()}</span>
          </div>
        )}
      </div>

      {/* Target & Operation Details */}
      <div className="mt-4 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] p-3 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center space-x-2">
            <span className="text-[var(--forge-text-muted)]">Tool:</span>
            <code className="rounded bg-[var(--forge-surface)] px-1.5 py-0.5 font-mono text-[var(--forge-accent)] border border-[var(--forge-border)]">
              {approval.tool_name}
            </code>
          </div>
          {targetPath && (
            <div className="flex items-center space-x-2">
              <span className="text-[var(--forge-text-muted)]">Target:</span>
              <code className="rounded bg-[var(--forge-surface)] px-1.5 py-0.5 font-mono text-[var(--forge-text-primary)] border border-[var(--forge-border)] truncate max-w-xs sm:max-w-md">
                {targetPath}
              </code>
            </div>
          )}
        </div>

        {/* Expandable Arguments */}
        <div>
          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            className="mt-1 flex items-center space-x-1 text-xs text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] transition-colors"
            aria-expanded={showDetails}
          >
            <span>{showDetails ? 'Hide execution arguments' : 'View full execution arguments'}</span>
            {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
          {showDetails && (
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-[var(--forge-surface)] p-2.5 font-mono text-xs text-[var(--forge-text-secondary)] border border-[var(--forge-border)]">
              {JSON.stringify(argsToDisplay, null, 2)}
            </pre>
          )}
        </div>
      </div>

      {/* Optional Reason Input */}
      <div className="mt-4">
        <label htmlFor={`approval-reason-${approval.id}`} className="block text-xs font-medium text-[var(--forge-text-secondary)] mb-1">
          Review notes / rationale (optional)
        </label>
        <input
          id={`approval-reason-${approval.id}`}
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Approved safe refactoring modification..."
          disabled={isSubmitting}
          className="w-full rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-3 py-1.5 text-xs text-[var(--forge-text-primary)] placeholder-[var(--forge-text-muted)] focus:border-[var(--forge-accent)] focus:outline-hidden focus:ring-1 focus:ring-[var(--forge-accent)] disabled:opacity-50"
        />
      </div>

      {/* Error alert */}
      {error && (
        <div className="mt-3 flex items-center space-x-2 rounded border border-[var(--forge-danger-border)] bg-[var(--forge-danger-surface)] p-2.5 text-xs text-[var(--forge-danger)]">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-4 flex items-center justify-end space-x-3">
        <button
          type="button"
          onClick={handleDeny}
          disabled={isSubmitting}
          className="inline-flex items-center space-x-1.5 rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-3.5 py-1.5 text-xs font-medium text-[var(--forge-text-secondary)] hover:text-[var(--forge-danger)] hover:border-[var(--forge-danger-border)] hover:bg-[var(--forge-danger-surface)] focus:outline-hidden focus-visible:ring-1 focus-visible:ring-[var(--forge-danger)] disabled:opacity-50 transition-colors"
        >
          {isSubmitting && actionType === 'deny' ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Denying…</span>
            </>
          ) : (
            <>
              <X className="h-3.5 w-3.5" />
              <span>Deny</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={handleApprove}
          disabled={isSubmitting}
          className="inline-flex items-center space-x-1.5 rounded bg-[var(--forge-accent)] px-4 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] hover:bg-[var(--forge-accent-hover)] focus:outline-hidden focus-visible:ring-1 focus-visible:ring-[var(--forge-accent)] disabled:opacity-50 transition-colors shadow-xs"
        >
          {isSubmitting && actionType === 'approve' ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--forge-accent-foreground)]" />
              <span>Approving…</span>
            </>
          ) : (
            <>
              <Check className="h-3.5 w-3.5 text-[var(--forge-accent-foreground)]" />
              <span>Approve & Resume</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
