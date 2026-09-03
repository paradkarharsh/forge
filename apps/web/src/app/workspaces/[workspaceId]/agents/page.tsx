import { WorkspaceAgentsView } from '@/components/agent/views/workspace-agents-view';

export function generateStaticParams() {
  return [
    { workspaceId: 'default' },
    { workspaceId: '00000000-0000-0000-0000-000000000001' },
  ];
}

export default async function WorkspaceAgentsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  return <WorkspaceAgentsView workspaceId={workspaceId} />;
}
