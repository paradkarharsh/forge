"""Safe read-only git client for repository intelligence.

Implements ``GitClient`` against a cloned repository's git object store
using ``git ls-tree``, ``git show``, and ``git diff``. All commands use
argument arrays (no shell interpolation), validated repository-relative
paths, and timeouts. ``--no-pager`` and ``-c core.quotepath=false`` keep
output deterministic; ``-z`` avoids quoting issues with unusual paths.
"""
import asyncio
import logging

from forge_api.domain.errors import DomainError
from forge_api.domain.indexing import (
    DiffEntry,
    DiscoveredFile,
    normalize_repo_path,
    validate_revision,
)
from forge_api.infrastructure.language_map import detect_language

logger = logging.getLogger(__name__)

_MAX_REV_LEN = 40


class SubprocessGitClient:
    """``GitClient`` implementation using safe subprocess git commands."""

    def __init__(self, timeout_seconds: int = 30) -> None:
        self._timeout = timeout_seconds

    async def _run(
        self, args: list[str], *, timeout: int | None = None
    ) -> tuple[bytes, bytes]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout or self._timeout
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise DomainError("git command timed out", code="git_timeout") from None
        if proc.returncode != 0:
            raise DomainError(
                f"git command failed: {stderr.decode('utf-8', 'replace').strip()}",
                code="git_error",
            )
        return stdout, stderr

    def _git(self, repo_dir: str, *args: str) -> list[str]:
        return [
            "git",
            "-c",
            "core.quotepath=false",
            "--no-pager",
            "-C",
            repo_dir,
            *args,
        ]

    async def head_revision(self, repo_dir: str) -> str:
        stdout, _ = await self._run(self._git(repo_dir, "rev-parse", "HEAD"))
        rev = stdout.decode("utf-8", "replace").strip()
        if not rev or len(rev) > _MAX_REV_LEN:
            raise DomainError("failed to resolve repository HEAD", code="git_error")
        return validate_revision(rev)

    async def list_tree(self, repo_dir: str, rev: str = "HEAD") -> list[DiscoveredFile]:
        rev = validate_revision(rev)
        stdout, _ = await self._run(
            self._git(repo_dir, "ls-tree", "-r", "-z", "--long", rev)
        )
        files: list[DiscoveredFile] = []
        for entry in stdout.split(b"\0"):
            if not entry:
                continue
            header, _, path_bytes = entry.partition(b"\t")
            parts = header.split(b" ")
            if len(parts) < 4:
                continue
            _mode, obj_type, _oid, size = parts[0], parts[1], parts[2], parts[3]
            if obj_type != b"blob":
                continue
            path = path_bytes.decode("utf-8", "replace")
            try:
                path = normalize_repo_path(path)
            except ValueError:
                logger.warning("Skipping unsafe repo path %r", path)
                continue
            try:
                size_bytes = int(size)
            except ValueError:
                size_bytes = None
            files.append(
                DiscoveredFile(
                    path=path,
                    language=detect_language(path),
                    size_bytes=size_bytes,
                )
            )
        return files

    async def read_file(self, repo_dir: str, rev: str, path: str) -> bytes:
        rev = validate_revision(rev)
        path = normalize_repo_path(path)
        stdout, _ = await self._run(
            self._git(repo_dir, "show", f"{rev}:{path}")
        )
        return stdout

    async def diff_name_status(
        self, repo_dir: str, old_rev: str, new_rev: str
    ) -> list[DiffEntry]:
        old_rev = validate_revision(old_rev)
        new_rev = validate_revision(new_rev)
        stdout, _ = await self._run(
            self._git(
                repo_dir, "diff", "--name-status", "-z", old_rev, new_rev
            )
        )
        tokens = [t.decode("utf-8", "replace") for t in stdout.split(b"\0")]
        entries: list[DiffEntry] = []
        i = 0
        while i < len(tokens):
            status_field = tokens[i]
            if not status_field:
                i += 1
                continue
            status = status_field[0]
            if status in ("R", "C") and len(status_field) > 1:
                status = status_field[0]
            if status in ("R", "C"):
                if i + 2 >= len(tokens):
                    break
                old_path = tokens[i + 1]
                new_path = tokens[i + 2]
                try:
                    entries.append(
                        DiffEntry(
                            status=status,
                            path=normalize_repo_path(new_path),
                            old_path=normalize_repo_path(old_path),
                        )
                    )
                except ValueError:
                    logger.warning("Skipping unsafe rename paths")
                i += 3
            else:
                if i + 1 >= len(tokens):
                    break
                path = tokens[i + 1]
                try:
                    entries.append(
                        DiffEntry(
                            status=status,
                            path=normalize_repo_path(path),
                        )
                    )
                except ValueError:
                    logger.warning("Skipping unsafe diff path %r", path)
                i += 2
        return entries