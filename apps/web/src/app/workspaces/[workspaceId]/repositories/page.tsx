import { WorkspaceRepositoriesView } from '@/components/workspace/workspace-repositories-view';

export function generateStaticParams() {
  return [{ workspaceId: 'default' }];
}

export default async function WorkspaceRepositoriesPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  return <WorkspaceRepositoriesView workspaceId={workspaceId} />;
}
