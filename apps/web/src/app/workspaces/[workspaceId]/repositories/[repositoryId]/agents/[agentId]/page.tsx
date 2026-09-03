import { AgentSessionView } from '@/components/agent/views/agent-session-view';

export function generateStaticParams() {
  return [{ workspaceId: 'default', repositoryId: 'default', agentId: 'default' }];
}

export default async function RepositoryAgentSessionPage({
  params,
}: {
  params: Promise<{ workspaceId: string; repositoryId: string; agentId: string }>;
}) {
  const { workspaceId, repositoryId, agentId } = await params;
  return (
    <AgentSessionView
      workspaceId={workspaceId}
      repositoryId={repositoryId}
      agentId={agentId}
    />
  );
}
