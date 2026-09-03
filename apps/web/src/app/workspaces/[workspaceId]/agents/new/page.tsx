import { CreateAgentForm } from '@/components/agent/create-agent-form';
import { AppShell } from '@/components/layout/app-shell';

export function generateStaticParams() {
  return [{ workspaceId: 'default' }];
}

export default async function NewWorkspaceAgentPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;

  return (
    <AppShell workspaceId={workspaceId}>
      <div className="max-w-4xl w-full mx-auto p-4 sm:p-6 space-y-5">
        <div className="space-y-0.5">
          <h1 className="text-xl font-semibold tracking-tight text-[var(--forge-text-primary)]">
            Launch New Agent
          </h1>
          <p className="text-xs text-[var(--forge-text-secondary)]">
            Formulate an engineering objective for autonomous plan generation, AST inspection, and tool execution.
          </p>
        </div>

        <div className="rounded-lg border border-[var(--forge-border)] bg-[var(--forge-surface)] p-5 shadow-xs">
          <CreateAgentForm workspaceId={workspaceId} />
        </div>
      </div>
    </AppShell>
  );
}
