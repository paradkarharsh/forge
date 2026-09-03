import { WorkspaceRepositoriesView } from '@/components/workspace/workspace-repositories-view';

export function generateStaticParams() {
  return [
    { workspaceId: 'default' },
    { workspaceId: '00000000-0000-0000-0000-000000000001' },
  ];
}

export default async function WorkspaceRepositoriesPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  return <WorkspaceRepositoriesView workspaceId={workspaceId} />;
}
