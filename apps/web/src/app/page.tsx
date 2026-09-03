import { ArrowRight, Bot, Cpu, FolderGit2, ShieldCheck, Sparkles } from 'lucide-react';
import Link from 'next/link';

export default function HomePage() {
  // Default demo workspace for immediate navigation
  const demoWorkspaceId = '00000000-0000-0000-0000-000000000001';

  return (
    <main
      aria-label="Forge workspace initialization"
      className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans"
    >
      {/* Top Bar */}
      <header className="h-16 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md px-6 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white font-mono text-sm font-black shadow-xs">
            F
          </div>
          <span className="font-bold text-base tracking-tight text-zinc-100">
            Forge
          </span>
          <span className="ml-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-mono text-indigo-300">
            FP8 Agentic Engine
          </span>
        </div>

        <Link
          href={`/workspaces/${demoWorkspaceId}/agents`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 border border-zinc-800 px-3.5 py-1.5 text-xs font-medium text-zinc-200 hover:text-white hover:border-zinc-700 transition-colors"
        >
          <span>Open Workspace</span>
          <ArrowRight className="h-3.5 w-3.5 text-zinc-400" />
        </Link>
      </header>

      {/* Hero Section */}
      <div className="flex-1 max-w-5xl w-full mx-auto px-6 py-16 flex flex-col justify-center space-y-10">
        <div className="space-y-4 max-w-2xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-300">
            <Sparkles className="h-3.5 w-3.5" />
            <span>AI-Native Software Engineering Workspace</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-zinc-100 leading-tight">
            Autonomous Agents with Durable Engineering Memory.
          </h1>

          <p className="text-sm sm:text-base text-zinc-400 leading-relaxed">
            Forge orchestrates repository-aware AI agents through a Clean Architecture runtime. Formulate multi-step plans, inspect symbols, execute safe terminal tools, and review human approvals in one unified workspace.
          </p>
        </div>

        {/* Quick Actions */}
        <div className="flex flex-wrap items-center gap-4">
          <Link
            href={`/workspaces/${demoWorkspaceId}/agents/new`}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 px-5 py-3 text-sm font-semibold text-white shadow-lg transition-colors"
          >
            <Bot className="h-4 w-4" />
            <span>Launch New Agent</span>
            <ArrowRight className="h-4 w-4" />
          </Link>

          <Link
            href={`/workspaces/${demoWorkspaceId}/agents`}
            className="inline-flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-800 px-5 py-3 text-sm font-semibold text-zinc-200 hover:text-white transition-colors"
          >
            <span>View Active Agents</span>
          </Link>
        </div>

        {/* Feature Highlights Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6 border-t border-zinc-800/80">
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-5 space-y-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Cpu className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-200">
              Bounded Execution Loop
            </h3>
            <p className="text-xs text-zinc-500 leading-relaxed">
              Durable execution limits enforced at the backend layer (900s wall time, 30 LLM calls, 50 tool calls).
            </p>
          </div>

          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-5 space-y-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-200">
              Human-in-the-Loop Safety
            </h3>
            <p className="text-xs text-zinc-500 leading-relaxed">
              High-risk tools require explicit human authorization with SHA-256 argument verification.
            </p>
          </div>

          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-5 space-y-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <FolderGit2 className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-200">
              Real-time SSE Streaming
            </h3>
            <p className="text-xs text-zinc-500 leading-relaxed">
              Live Redis pub/sub event handoff with 500-event replay buffer, secret scrubbing, and automatic reconnect.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
