import { WorkspaceAgentsView } from '@/components/agent/views/workspace-agents-view';

export function generateStaticParams() {
  return [{ workspaceId: 'default' }];
}

export default async function WorkspaceAgentsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  return <WorkspaceAgentsView workspaceId={workspaceId} />;
}
