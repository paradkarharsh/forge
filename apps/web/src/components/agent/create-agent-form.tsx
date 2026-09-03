'use client';

import {
  AlertCircle,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Cpu,
  Gauge,
  Loader2,
  Sparkles,
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
        // If run fails, the session is still created; user can view or retry
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
    <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
      {/* Error alert */}
      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 flex items-start gap-3 text-xs text-rose-200">
          <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold text-rose-300">Creation Failed</span>
            <p className="font-mono">{error}</p>
          </div>
        </div>
      )}

      {/* Objective Input */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label
            htmlFor="agent-objective"
            className="text-xs font-semibold text-zinc-200 uppercase tracking-wider flex items-center gap-1.5"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
            <span>Task Instruction & Objective</span>
          </label>
          <span
            className={`text-[11px] font-mono ${
              charCount > 10000
                ? 'text-rose-400'
                : charCount > 8000
                ? 'text-amber-400'
                : 'text-zinc-500'
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
          className="w-full rounded-xl border border-zinc-800 bg-zinc-900/60 p-3.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-indigo-500 focus:outline-hidden transition-colors resize-y leading-relaxed font-sans"
        />

        <p className="text-[11px] text-zinc-500 leading-normal">
          Be specific about the expected outcomes, modified files, or test commands. The agent will formulate an execution plan, inspect context, and request approval before high-risk changes.
        </p>
      </div>

      {/* Model Selection */}
      <div className="space-y-2">
        <label
          htmlFor="agent-model"
          className="text-xs font-semibold text-zinc-200 uppercase tracking-wider flex items-center gap-1.5"
        >
          <Cpu className="h-3.5 w-3.5 text-zinc-400" />
          <span>LLM Model</span>
        </label>
        <select
          id="agent-model"
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          className="w-full sm:w-80 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs text-zinc-200 focus:border-indigo-500 focus:outline-hidden transition-colors"
        >
          {AVAILABLE_MODELS.map((m) => (
            <option key={m.id} value={m.id} className="bg-zinc-950 text-zinc-200">
              {m.label}
            </option>
          ))}
        </select>
      </div>

      {/* Advanced Execution Limits Collapsible */}
      <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4 space-y-4">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center justify-between w-full text-left text-xs font-semibold text-zinc-300 hover:text-zinc-100 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Gauge className="h-4 w-4 text-zinc-500" />
            <span>Advanced Execution Limits</span>
          </div>
          {showAdvanced ? (
            <ChevronDown className="h-4 w-4 text-zinc-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-zinc-500" />
          )}
        </button>

        {showAdvanced && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-zinc-800/60 text-xs">
            <div className="space-y-1.5">
              <label htmlFor="wall-time-limit" className="text-zinc-400 font-medium">
                Max Wall Time (seconds)
              </label>
              <input
                id="wall-time-limit"
                type="number"
                min={60}
                max={3600}
                value={maxWallTime}
                onChange={(e) => setMaxWallTime(Number(e.target.value))}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-200 font-mono focus:border-indigo-500 focus:outline-hidden"
              />
              <span className="text-[10px] text-zinc-600 block">Default: 900s (15 min)</span>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="llm-calls-limit" className="text-zinc-400 font-medium">
                Max LLM Calls
              </label>
              <input
                id="llm-calls-limit"
                type="number"
                min={1}
                max={50}
                value={maxLlmCalls}
                onChange={(e) => setMaxLlmCalls(Number(e.target.value))}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-200 font-mono focus:border-indigo-500 focus:outline-hidden"
              />
              <span className="text-[10px] text-zinc-600 block">Default: 30 calls</span>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="tool-calls-limit" className="text-zinc-400 font-medium">
                Max Tool Calls
              </label>
              <input
                id="tool-calls-limit"
                type="number"
                min={1}
                max={100}
                value={maxToolCalls}
                onChange={(e) => setMaxToolCalls(Number(e.target.value))}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-200 font-mono focus:border-indigo-500 focus:outline-hidden"
              />
              <span className="text-[10px] text-zinc-600 block">Default: 50 calls</span>
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
          className="rounded-lg px-4 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors disabled:opacity-50"
        >
          Cancel
        </button>

        <button
          type="submit"
          disabled={!isValid || isSubmitting}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-5 py-2.5 text-xs font-semibold text-white shadow-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
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
