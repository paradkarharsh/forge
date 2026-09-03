import { AgentSessionView } from '@/components/agent/views/agent-session-view';

export function generateStaticParams() {
  return [{ workspaceId: 'default', agentId: 'default' }];
}

export default async function WorkspaceAgentSessionPage({
  params,
}: {
  params: Promise<{ workspaceId: string; agentId: string }>;
}) {
  const { workspaceId, agentId } = await params;
  return (
    <AgentSessionView
      workspaceId={workspaceId}
      agentId={agentId}
    />
  );
}
