'use client';

import {
  AlertCircle,
  ArrowRight,
  Bot,
  ChevronDown,
  ChevronRight,
  Cpu,
  Gauge,
  Loader2,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { agentService } from '../../lib/api/agent';
import { ApiClientError } from '../../lib/api/client';
import type { CreateAgentSessionPayload } from '../../lib/api/types';

interface CreateAgentFormProps {
  readonly workspaceId: string;
  readonly repositoryId?: string | null;
}

const AVAILABLE_MODELS = [
  { id: 'default', label: 'Default (System standard)' },
  { id: 'gpt-4o', label: 'GPT-4o' },
  { id: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
  { id: 'gpt-4o-mini', label: 'GPT-4o Mini (Fast)' },
];

export function CreateAgentForm({
  workspaceId,
  repositoryId,
}: CreateAgentFormProps) {
  const router = useRouter();

  const [objective, setObjective] = useState('');
  const [selectedModel, setSelectedModel] = useState('default');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Limits
  const [maxWallTime, setMaxWallTime] = useState(900);
  const [maxLlmCalls, setMaxLlmCalls] = useState(30);
  const [maxToolCalls, setMaxToolCalls] = useState(50);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const charCount = objective.trim().length;
  const isValid = charCount >= 1 && charCount <= 10000;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const payload: CreateAgentSessionPayload = {
        objective: objective.trim(),
        repository_id: repositoryId || null,
        model: selectedModel === 'default' ? null : selectedModel,
        limits: {
          max_wall_time_seconds: Number(maxWallTime) || 900,
          max_llm_calls: Number(maxLlmCalls) || 30,
          max_tool_calls: Number(maxToolCalls) || 50,
          max_output_bytes: 65536,
          max_observation_bytes: 8192,
        },
      };

      const session = await agentService.createSession(workspaceId, payload);

      // Automatically trigger execution dispatch
      try {
        await agentService.runSession(workspaceId, session.id);
      } catch (runErr) {
        console.warn('Initial session run dispatch failed:', runErr);
      }

      // Navigate to the newly created session workspace
      const targetPath = repositoryId
        ? `/workspaces/${workspaceId}/repositories/${repositoryId}/agents/${session.id}`
        : `/workspaces/${workspaceId}/agents/${session.id}`;

      router.push(targetPath);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(`${err.code}: ${err.message}`);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred while creating the agent.');
      }
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5 max-w-2xl">
      {/* Error alert */}
      {error && (
        <div className="rounded border border-[var(--forge-danger-border)] bg-[var(--forge-danger-surface)] p-3 flex items-start gap-2.5 text-xs text-[var(--forge-danger)]">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-semibold">Creation Failed</span>
            <p className="font-mono text-[11px]">{error}</p>
          </div>
        </div>
      )}

      {/* Objective Input */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label
            htmlFor="agent-objective"
            className="text-xs font-semibold text-[var(--forge-text-primary)] uppercase tracking-wider flex items-center gap-1.5"
          >
            <Bot className="h-3.5 w-3.5 text-[var(--forge-accent)]" />
            <span>Task Objective</span>
          </label>
          <span
            className={`text-[11px] font-mono ${
              charCount > 10000
                ? 'text-[var(--forge-danger)]'
                : charCount > 8000
                ? 'text-[var(--forge-warning)]'
                : 'text-[var(--forge-text-muted)]'
            }`}
          >
            {charCount.toLocaleString()} / 10,000
          </span>
        </div>

        <textarea
          id="agent-objective"
          rows={5}
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="E.g. Refactor the authentication service to use Argon2 hashing, update relevant unit tests, and verify the full test suite passes..."
          required
          className="w-full rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3 text-xs text-[var(--forge-text-primary)] placeholder-[var(--forge-text-muted)] focus:border-[var(--forge-accent)] focus:outline-hidden transition-colors resize-y leading-relaxed font-sans"
        />

        <p className="text-[11px] text-[var(--forge-text-muted)] leading-normal">
          Be specific about affected files, target symbols, and required validations. Forge agents formulate bounded plans and request approval before high-risk changes.
        </p>
      </div>

      {/* Model Selection */}
      <div className="space-y-1.5">
        <label
          htmlFor="agent-model"
          className="text-xs font-semibold text-[var(--forge-text-primary)] uppercase tracking-wider flex items-center gap-1.5"
        >
          <Cpu className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          <span>LLM Model</span>
        </label>
        <select
          id="agent-model"
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          className="w-full sm:w-72 rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] px-2.5 py-1.5 text-xs text-[var(--forge-text-primary)] focus:border-[var(--forge-accent)] focus:outline-hidden transition-colors"
        >
          {AVAILABLE_MODELS.map((m) => (
            <option key={m.id} value={m.id} className="bg-[var(--forge-surface)] text-[var(--forge-text-primary)]">
              {m.label}
            </option>
          ))}
        </select>
      </div>

      {/* Advanced Execution Limits Collapsible */}
      <div className="rounded border border-[var(--forge-border)] bg-[var(--forge-surface)] p-3.5 space-y-3">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center justify-between w-full text-left text-xs font-semibold text-[var(--forge-text-primary)] hover:text-[var(--forge-accent)] transition-colors"
        >
          <div className="flex items-center gap-2">
            <Gauge className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
            <span>Execution Limits</span>
          </div>
          {showAdvanced ? (
            <ChevronDown className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-[var(--forge-text-muted)]" />
          )}
        </button>

        {showAdvanced && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2.5 border-t border-[var(--forge-border-subtle)] text-xs">
            <div className="space-y-1">
              <label htmlFor="wall-time-limit" className="text-[var(--forge-text-secondary)] font-medium">
                Max Wall Time (s)
              </label>
              <input
                id="wall-time-limit"
                type="number"
                min={60}
                max={3600}
                value={maxWallTime}
                onChange={(e) => setMaxWallTime(Number(e.target.value))}
                className="w-full rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2.5 py-1 text-xs text-[var(--forge-text-primary)] font-mono focus:border-[var(--forge-accent)] focus:outline-hidden"
              />
              <span className="text-[10px] text-[var(--forge-text-muted)] block">Default: 900s</span>
            </div>

            <div className="space-y-1">
              <label htmlFor="llm-calls-limit" className="text-[var(--forge-text-secondary)] font-medium">
                Max LLM Calls
              </label>
              <input
                id="llm-calls-limit"
                type="number"
                min={1}
                max={50}
                value={maxLlmCalls}
                onChange={(e) => setMaxLlmCalls(Number(e.target.value))}
                className="w-full rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2.5 py-1 text-xs text-[var(--forge-text-primary)] font-mono focus:border-[var(--forge-accent)] focus:outline-hidden"
              />
              <span className="text-[10px] text-[var(--forge-text-muted)] block">Default: 30 calls</span>
            </div>

            <div className="space-y-1">
              <label htmlFor="tool-calls-limit" className="text-[var(--forge-text-secondary)] font-medium">
                Max Tool Calls
              </label>
              <input
                id="tool-calls-limit"
                type="number"
                min={1}
                max={100}
                value={maxToolCalls}
                onChange={(e) => setMaxToolCalls(Number(e.target.value))}
                className="w-full rounded border border-[var(--forge-border)] bg-[var(--forge-surface-secondary)] px-2.5 py-1 text-xs text-[var(--forge-text-primary)] font-mono focus:border-[var(--forge-accent)] focus:outline-hidden"
              />
              <span className="text-[10px] text-[var(--forge-text-muted)] block">Default: 50 calls</span>
            </div>
          </div>
        )}
      </div>

      {/* Submit Controls */}
      <div className="flex items-center justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={() => router.back()}
          disabled={isSubmitting}
          className="rounded px-3 py-1.5 text-xs font-medium text-[var(--forge-text-secondary)] hover:text-[var(--forge-text-primary)] transition-colors disabled:opacity-50"
        >
          Cancel
        </button>

        <button
          type="submit"
          disabled={!isValid || isSubmitting}
          className="inline-flex items-center gap-1.5 rounded bg-[var(--forge-accent)] px-4 py-1.5 text-xs font-semibold text-[var(--forge-accent-foreground)] hover:bg-[var(--forge-accent-hover)] shadow-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Initializing Agent...</span>
            </>
          ) : (
            <>
              <span>Launch Agent</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </>
          )}
        </button>
      </div>
    </form>
  );
}
