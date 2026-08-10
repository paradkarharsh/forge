"""Repository file discovery service.

Lists the tracked files of a cloned repository via the git port and
applies indexability filtering (vendor/generated/binary paths). The diff
capability backs incremental indexing on future sync events.
"""
from forge_api.domain.indexing import DiffEntry, DiscoveredFile, GitClient
from forge_api.infrastructure.language_map import is_indexable_path


class FileDiscoveryService:
    """Discovers indexable files in a repository tree."""

    def __init__(self, *, git: GitClient, max_files: int = 50_000) -> None:
        self._git = git
        self._max_files = max_files

    async def discover_files(
        self, repo_dir: str, rev: str = "HEAD"
    ) -> list[DiscoveredFile]:
        """Return indexable files (path, language, size) up to ``max_files``."""
        tree = await self._git.list_tree(repo_dir, rev)
        indexable = [f for f in tree if is_indexable_path(f.path)]
        return indexable[: self._max_files]

    async def diff(
        self, repo_dir: str, old_rev: str, new_rev: str
    ) -> list[DiffEntry]:
        """Return the file changes between two revisions."""
        return await self._git.diff_name_status(repo_dir, old_rev, new_rev)