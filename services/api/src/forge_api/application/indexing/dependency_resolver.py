"""Resolve parsed import paths to repository file paths.

Converts the ``target_path`` strings produced by the parser (e.g.
``src.auth.service``, ``./util``, ``crate::config``, ``fmt``) into
repository-relative file paths by matching against the set of files known
to be in the repository tree. Unresolvable targets are marked external.
Resolution is best-effort and language-aware; it never throws.
"""
import posixpath

# Extension candidates tried when a bare module path is resolved, per language,
# plus the directory index file name (python packages use __init__.py).
_LANG_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py", ".pyi"],
    "typescript": [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"],
    "tsx": [".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"],
    "rust": [".rs"],
    "go": [".go"],
}

_LANG_INDEX_NAME: dict[str, str] = {
    "python": "__init__",
    "typescript": "index",
    "tsx": "index",
    "javascript": "index",
    "rust": "mod",
}


def _resolve_candidates(
    base: str,
    repo_files: set[str],
    extensions: list[str],
    index_name: str | None,
) -> str | None:
    for ext in extensions:
        if base + ext in repo_files:
            return base + ext
    if index_name:
        for ext in extensions:
            index_candidate = posixpath.join(base, f"{index_name}{ext}")
            if index_candidate in repo_files:
                return index_candidate
    if base in repo_files:
        return base
    return None


class DependencyResolver:
    """Maps a parsed import path to a repository file path when possible."""

    def resolve(
        self,
        *,
        source_path: str,
        target_path: str,
        repo_files: set[str],
        language: str | None,
    ) -> tuple[str | None, bool]:
        """Return ``(resolved_file_path | None, is_external)``.

        ``None`` means the target could not be mapped to a repository file;
        ``is_external`` is True in that case (or when the target clearly
        refers to a third-party / stdlib module).
        """
        if language is None:
            return None, True
        extensions = _LANG_EXTENSIONS.get(language, [])
        index_name = _LANG_INDEX_NAME.get(language)
        source_dir = posixpath.dirname(source_path)

        base, relative = self._to_base(target_path, language)
        if base is None:
            return None, True

        if relative:
            full = posixpath.normpath(posixpath.join(source_dir, base))
            resolved = _resolve_candidates(full, repo_files, extensions, index_name)
        else:
            resolved = _resolve_candidates(base, repo_files, extensions, index_name)

        if resolved is not None:
            return resolved, False
        return None, True

    def _to_base(
        self, target_path: str, language: str
    ) -> tuple[str | None, bool]:
        """Convert an import path to a base repo path and a relative flag."""
        path = target_path.strip()
        if not path:
            return None, False

        if language == "python":
            # Dotted module paths must not be split on the last dot.
            depth = 0
            while path.startswith("."):
                depth += 1
                path = path[1:]
            if depth:
                if not path:
                    return None, False
                rel = posixpath.join(*([".."] * (depth - 1)), path.replace(".", "/"))
                return rel, True
            return path.replace(".", "/"), False

        base, ext = posixpath.splitext(path)
        if ext:
            path = base

        if language in ("javascript", "typescript", "tsx"):
            if path.startswith("."):
                return path, True
            return None, False  # bare specifiers are external

        if language == "rust":
            if path.startswith("crate::"):
                return path[len("crate::") :].replace("::", "/"), True
            if path.startswith("./") or path.startswith("self::"):
                return path.replace("::", "/"), True
            return None, False  # external crates

        if language == "go":
            return path, True

        return None, False