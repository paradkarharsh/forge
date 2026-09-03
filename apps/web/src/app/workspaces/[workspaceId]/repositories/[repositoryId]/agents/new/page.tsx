import { CreateAgentForm } from '@/components/agent/create-agent-form';
import { WorkspaceNav } from '@/components/layout/workspace-nav';

export function generateStaticParams() {
  return [{ workspaceId: 'default', repositoryId: 'default' }];
}

export default async function NewRepositoryAgentPage({
  params,
}: {
  params: Promise<{ workspaceId: string; repositoryId: string }>;
}) {
  const { workspaceId, repositoryId } = await params;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      <WorkspaceNav workspaceId={workspaceId} repositoryId={repositoryId} />

      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Launch New Agent
          </h1>
          <p className="text-xs text-zinc-400">
            Define an engineering objective for the agent to execute within this repository context.
          </p>
        </div>

        <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/30 p-6 shadow-xs">
          <CreateAgentForm
            workspaceId={workspaceId}
            repositoryId={repositoryId}
          />
        </div>
      </main>
    </div>
  );
}
