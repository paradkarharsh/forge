import { CreateAgentForm } from '@/components/agent/create-agent-form';
import { AppShell } from '@/components/layout/app-shell';

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
    <AppShell workspaceId={workspaceId} repositoryId={repositoryId}>
      <div className="max-w-4xl w-full mx-auto p-4 sm:p-6 space-y-5">
        <div className="space-y-0.5">
          <h1 className="text-xl font-semibold tracking-tight text-[var(--forge-text-primary)]">
            Launch New Agent
          </h1>
          <p className="text-xs text-[var(--forge-text-secondary)] font-mono">
            Repository: {repositoryId}
          </p>
        </div>

        <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 shadow-xs">
          <CreateAgentForm
            workspaceId={workspaceId}
            repositoryId={repositoryId}
          />
        </div>
      </div>
    </AppShell>
  );
}
