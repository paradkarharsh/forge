import { WorkspaceDashboardView } from '@/components/workspace/workspace-dashboard-view';

export function generateStaticParams() {
  return [{ workspaceId: 'default' }];
}

export default async function WorkspaceDashboardPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  return <WorkspaceDashboardView workspaceId={workspaceId} />;
}
