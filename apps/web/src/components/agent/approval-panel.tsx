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
      className="mb-6 rounded-xl border border-amber-500/40 bg-gradient-to-b from-amber-950/20 via-neutral-900 to-neutral-900/90 p-5 shadow-xl shadow-amber-950/20"
    >
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start space-x-3.5">
          <div className="rounded-lg bg-amber-500/10 p-2 text-amber-400 ring-1 ring-amber-500/30">
            <ShieldAlert className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center space-x-2.5">
              <h3 className="text-base font-semibold text-white">
                Human Approval Required
              </h3>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider ${
                  riskLevel === 'CRITICAL'
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}
              >
                {riskLevel} Risk
              </span>
            </div>
            <p className="mt-1 text-sm text-neutral-300">
              This action requires your approval before Forge executes it.
            </p>
          </div>
        </div>

        {approval.expires_at && (
          <div className="flex items-center space-x-1.5 text-xs text-neutral-400 bg-neutral-800/80 px-2.5 py-1 rounded-md border border-neutral-700/60 self-start">
            <Clock className="h-3.5 w-3.5 text-neutral-400" />
            <span>Expires: {new Date(approval.expires_at).toLocaleTimeString()}</span>
          </div>
        )}
      </div>

      {/* Target & Operation Details */}
      <div className="mt-4 rounded-lg border border-neutral-800 bg-neutral-950/70 p-3.5 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center space-x-2">
            <span className="text-neutral-400">Tool:</span>
            <code className="rounded bg-neutral-900 px-2 py-0.5 font-mono text-emerald-400 border border-neutral-800">
              {approval.tool_name}
            </code>
          </div>
          {targetPath && (
            <div className="flex items-center space-x-2">
              <span className="text-neutral-400">Target:</span>
              <code className="rounded bg-neutral-900 px-2 py-0.5 font-mono text-sky-300 border border-neutral-800 truncate max-w-xs sm:max-w-md">
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
            className="mt-1 flex items-center space-x-1 text-xs text-neutral-400 hover:text-white transition-colors"
            aria-expanded={showDetails}
          >
            <span>{showDetails ? 'Hide execution arguments' : 'View full execution arguments'}</span>
            {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
          {showDetails && (
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-neutral-900/90 p-2.5 font-mono text-xs text-neutral-300 border border-neutral-800">
              {JSON.stringify(argsToDisplay, null, 2)}
            </pre>
          )}
        </div>
      </div>

      {/* Optional Reason Input */}
      <div className="mt-4">
        <label htmlFor={`approval-reason-${approval.id}`} className="block text-xs font-medium text-neutral-400 mb-1">
          Review notes / rationale (optional)
        </label>
        <input
          id={`approval-reason-${approval.id}`}
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Approved safe test modification..."
          disabled={isSubmitting}
          className="w-full rounded-lg border border-neutral-700 bg-neutral-900/90 px-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 disabled:opacity-50"
        />
      </div>

      {/* Error alert */}
      {error && (
        <div className="mt-3 flex items-center space-x-2 rounded-lg border border-rose-500/40 bg-rose-950/40 p-2.5 text-xs text-rose-300">
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-4 flex items-center justify-end space-x-3">
        <button
          type="button"
          onClick={handleDeny}
          disabled={isSubmitting}
          className="inline-flex items-center space-x-1.5 rounded-lg border border-rose-500/40 bg-rose-950/20 px-4 py-2 text-xs font-medium text-rose-300 hover:bg-rose-900/40 focus:outline-none focus:ring-2 focus:ring-rose-500 disabled:opacity-50 transition-colors"
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
          className="inline-flex items-center space-x-1.5 rounded-lg border border-emerald-500/50 bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-950/40 hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:opacity-50 transition-colors"
        >
          {isSubmitting && actionType === 'approve' ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Approving…</span>
            </>
          ) : (
            <>
              <Check className="h-3.5 w-3.5" />
              <span>Approve & Resume</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
