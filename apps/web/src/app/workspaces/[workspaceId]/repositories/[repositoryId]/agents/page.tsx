import { RepositoryAgentsView } from '@/components/agent/views/repository-agents-view';

export function generateStaticParams() {
  return [{ workspaceId: 'default', repositoryId: 'default' }];
}

export default async function RepositoryAgentsPage({
  params,
}: {
  params: Promise<{ workspaceId: string; repositoryId: string }>;
}) {
  const { workspaceId, repositoryId } = await params;
  return (
    <RepositoryAgentsView
      workspaceId={workspaceId}
      repositoryId={repositoryId}
    />
  );
}
