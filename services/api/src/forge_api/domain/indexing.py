"""Repository intelligence domain model.

Persistence-neutral records and ports for indexing a cloned repository:
files, symbols, dependencies, chunks, and their embeddings. Also defines
the parser and embedding provider ports that the application layer depends
on so tree-sitter and embedding libraries stay in infrastructure.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

# ─── Enums ────────────────────────────────────────────────────────────


class IndexStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    STALE = "stale"


class SymbolKind(StrEnum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    INTERFACE = "interface"
    TYPE = "type"
    ENUM = "enum"
    CONSTANT = "constant"
    MODULE = "module"


class DependencyKind(StrEnum):
    IMPORT = "import"
    REQUIRE = "require"
    FROM = "from"
    INCLUDE = "include"
    USE = "use"


# ─── Records ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FileRecord:
    id: UUID
    repository_id: UUID
    path: str
    language: str | None
    size_bytes: int
    line_count: int | None
    commit_hash: str
    content_hash: str
    indexed_at: datetime


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    id: UUID
    file_id: UUID
    repository_id: UUID
    name: str
    kind: SymbolKind
    signature: str | None
    line_start: int
    line_end: int | None
    parent_symbol_id: UUID | None


@dataclass(frozen=True, slots=True)
class DependencyRecord:
    id: UUID
    repository_id: UUID
    source_file_id: UUID
    target_path: str
    target_file_id: UUID | None
    kind: DependencyKind
    is_external: bool


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    id: UUID
    file_id: UUID
    repository_id: UUID
    chunk_index: int
    content: str
    line_start: int
    line_end: int
    token_count: int
    embedding: list[float] | None = field(default=None)


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """A file discovered in a repository tree prior to content extraction."""

    path: str
    language: str | None
    size_bytes: int | None


@dataclass(frozen=True, slots=True)
class DiffEntry:
    """A single file change reported by ``git diff --name-status``.

    ``status`` is the single-letter git status (A/M/D/R). For renames,
    ``old_path`` is the previous path and ``path`` the new one.
    """

    status: str
    path: str
    old_path: str | None = None


@dataclass(frozen=True, slots=True)
class IndexStats:
    """Summary of a completed indexing run."""

    files_indexed: int
    files_skipped: int
    symbols: int
    dependencies: int
    chunks: int
    embeddings_created: int
    parse_errors: int


@dataclass(frozen=True, slots=True)
class Chunk:
    """A single chunk of file content ready for embedding."""

    content: str
    line_start: int
    line_end: int
    token_count: int


@dataclass(frozen=True, slots=True)
class IndexingConfig:
    """Tunable limits for a repository indexing run."""

    max_file_bytes: int = 512 * 1024
    max_files: int = 50_000
    chunk_tokens: int = 256
    chunk_overlap: int = 32
    embedding_batch_size: int = 64
    timeout_seconds: int = 1_800


# ─── Parser port ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ParsedSymbol:
    name: str
    kind: SymbolKind
    signature: str | None
    line_start: int
    line_end: int | None
    children: tuple["ParsedSymbol", ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedDependency:
    target_path: str
    kind: DependencyKind


@dataclass(frozen=True, slots=True)
class ParseResult:
    symbols: tuple[ParsedSymbol, ...]
    dependencies: tuple[ParsedDependency, ...]
    errors: tuple[str, ...] = ()


class TreeSitterParser(Protocol):
    """Parses source code into symbols and dependencies.

    Implementations use tree-sitter; the application layer only sees this
    protocol so parsing libraries stay in infrastructure.
    """

    def parse(self, content: str, language: str) -> ParseResult:
        """Parse ``content`` for ``language``. Never raises on parse errors."""
        ...

    def supported_languages(self) -> set[str]:
        """Languages this parser can handle."""
        ...


# ─── Embedding port ───────────────────────────────────────────────────


class EmbeddingProvider(Protocol):
    """Converts text into embedding vectors.

    A ``NullEmbedder`` implementation returns None embeddings so the
    system works fully with embeddings disabled.
    """

    async def embed(self, texts: list[str]) -> list[list[float] | None]:
        """Embed ``texts``; a disabled provider returns all-None vectors."""
        ...

    def dimension(self) -> int | None:
        """Vector dimension, or None when embeddings are disabled."""
        ...


# ─── Git port ─────────────────────────────────────────────────────────


class GitClient(Protocol):
    """Safe read-only access to a cloned repository's git object store.

    Application services depend on this protocol so subprocess and path
    handling stay in infrastructure. All commands use argument arrays,
    validated repository-relative paths, and timeouts.
    """

    async def head_revision(self, repo_dir: str) -> str:
        """Return the HEAD revision hash."""
        ...

    async def list_tree(self, repo_dir: str, rev: str = "HEAD") -> list[DiscoveredFile]:
        """List all tracked files (blobs) in ``rev`` with size metadata."""
        ...

    async def read_file(self, repo_dir: str, rev: str, path: str) -> bytes:
        """Return the raw content of ``path`` at ``rev``."""
        ...

    async def diff_name_status(
        self, repo_dir: str, old_rev: str, new_rev: str
    ) -> list[DiffEntry]:
        """Return added/modified/deleted/renamed entries between revisions."""
        ...


# ─── Path / revision validation ───────────────────────────────────────


def normalize_repo_path(path: str) -> str:
    """Validate and normalize a repository-relative path.

    Rejects absolute paths, backslashes, empty paths, and ``..``/``.``
    traversal so untrusted repository paths can never escape the repo.
    Returns the normalized forward-slash path.
    """
    if not path or not path.strip():
        raise ValueError("path must not be empty")
    if "\\" in path:
        raise ValueError("backslashes are not allowed in repository paths")
    if path.startswith("/"):
        raise ValueError("absolute paths are not allowed")
    parts = path.split("/")
    if any(part in ("..", ".") for part in parts):
        raise ValueError("path traversal is not allowed")
    return path


def validate_revision(rev: str) -> str:
    """Validate a git revision argument before use in a subprocess."""
    if rev == "HEAD":
        return rev
    if len(rev) not in range(4, 41) or not all(
        c in "0123456789abcdef" for c in rev
    ):
        raise ValueError("invalid revision")
    return rev
