"""Language detection from repository file paths.

Maps file extensions to the tree-sitter language names understood by
``ForgeTreeSitterParser``, and identifies files worth indexing.
"""
import os

# Extension -> parser language name.
_LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".rs": "rust",
    ".go": "go",
}

# Path segments that mark a file as vendor/generated/dependency code.
_SKIP_PATH_SEGMENTS = frozenset(
    {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "vendor",
        "__pycache__",
        ".next",
        "dist",
        "build",
        "target",  # Rust build dir
        ".cache",
        ".pytest_cache",
        "coverage",
    }
)

# Extensions that are never indexable as source (binaries, images, archives).
_SKIP_EXTENSIONS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
        ".pdf", ".zip", ".gz", ".tar", ".tgz", ".bz2", ".7z", ".rar",
        ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".class", ".jar",
        ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".avi",
        ".pyc", ".pyo", ".pyd", ".whl", ".lock",
    }
)


def detect_language(path: str) -> str | None:
    """Return the parser language for ``path``, or None if unknown."""
    ext = os.path.splitext(path)[1].lower()
    return _LANGUAGE_BY_EXTENSION.get(ext)


def is_indexable_path(path: str) -> bool:
    """Return True when ``path`` should be considered for indexing.

    Rejects hidden/vendor segments and obviously non-source extensions.
    Paths are repository-relative and normalized before this is called.
    """
    parts = path.split("/")
    if any(seg in _SKIP_PATH_SEGMENTS for seg in parts):
        return False
    if os.path.basename(path).startswith("."):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext in _SKIP_EXTENSIONS:
        return False
    return True