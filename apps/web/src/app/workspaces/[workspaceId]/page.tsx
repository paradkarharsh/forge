import { WorkspaceDashboardView } from '@/components/workspace/workspace-dashboard-view';

export function generateStaticParams() {
  return [
    { workspaceId: 'default' },
    { workspaceId: '00000000-0000-0000-0000-000000000001' },
  ];
}

export default async function WorkspaceDashboardPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  return <WorkspaceDashboardView workspaceId={workspaceId} />;
}
