"""Repository and code reading tools for the FP8 Agentic Engine."""
import logging
import os
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from forge_api.domain.errors import ValidationError
from forge_api.domain.tool import (
    RiskLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
    redact_secrets,
    safe_resolve_repo_path,
)

logger = logging.getLogger(__name__)

_IGNORE_DIRS = frozenset({
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".ruff_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".turbo",
    ".next",
})


class RepositoryListFilesTool:
    """Tool: repository.list_files."""

    name = "repository.list_files"
    description = "List files and directories in the repository with size and relative paths."
    category = ToolCategory.REPOSITORY
    risk_level = RiskLevel.READ_ONLY
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional subdirectory to list within the repository",
                "default": "",
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to list recursively (default: True)",
                "default": True,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of files to return (default: 100)",
                "default": 100,
            },
        },
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "files": {"type": "array", "items": {"type": "string"}},
            "total": {"type": "integer"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        path = input_data.get("path", "")
        limit = input_data.get("limit", 100)
        recursive = input_data.get("recursive", True)
        if not isinstance(path, str):
            raise ValidationError("'path' must be a string.", code="invalid_input")
        if not isinstance(limit, int) or limit <= 0:
            limit = 100
        return {"path": path, "recursive": bool(recursive), "limit": min(limit, 500)}

    async def execute(
        self, context: ToolExecutionContext, input_data: dict[str, Any]
    ) -> ToolResult:
        if not context.repo_root:
            return ToolResult(
                success=False,
                output="No repository root directory available in execution context.",
                error="missing_repo_root",
            )

        validated = self.validate(input_data)
        rel_subpath = validated["path"]
        limit = validated["limit"]
        recursive = validated["recursive"]

        try:
            target_dir = (
                safe_resolve_repo_path(context.repo_root, rel_subpath)
                if rel_subpath
                else Path(context.repo_root).resolve()
            )
        except ValidationError as exc:
            return ToolResult(success=False, output=exc.message, error=exc.code)

        if not target_dir.exists():
            return ToolResult(
                success=False,
                output=f"Directory '{rel_subpath}' does not exist.",
                error="not_found",
            )

        repo_root_path = Path(context.repo_root).resolve()
        files: list[str] = []

        if recursive:
            for root, dirs, filenames in os.walk(target_dir):
                # Filter ignore dirs in-place
                dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
                for fname in filenames:
                    if fname.startswith("."):
                        continue
                    full_p = Path(root) / fname
                    try:
                        rel = full_p.relative_to(repo_root_path).as_posix()
                        files.append(rel)
                    except ValueError:
                        continue
                    if len(files) >= limit:
                        break
                if len(files) >= limit:
                    break
        else:
            for item in sorted(target_dir.iterdir()):
                if item.name.startswith(".") or item.name in _IGNORE_DIRS:
                    continue
                try:
                    rel = item.relative_to(repo_root_path).as_posix()
                    files.append(rel + ("/" if item.is_dir() else ""))
                except ValueError:
                    continue
                if len(files) >= limit:
                    break

        files.sort()
        output_str = f"Found {len(files)} files:\n" + "\n".join(f"- {f}" for f in files)
        return ToolResult(
            success=True,
            output=output_str,
            data={"files": files, "total": len(files)},
        )


class RepositoryReadFileTool:
    """Tool: repository.read_file."""

    name = "repository.read_file"
    description = "Read the contents of a file in the repository with optional line slicing."
    category = ToolCategory.REPOSITORY
    risk_level = RiskLevel.READ_ONLY
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository-relative path of the file to read",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional 1-based start line (inclusive)",
            },
            "end_line": {
                "type": "integer",
                "description": "Optional 1-based end line (inclusive)",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "total_lines": {"type": "integer"},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        path = input_data.get("path")
        if not path or not isinstance(path, str):
            raise ValidationError(
                "'path' is required and must be a non-empty string.",
                code="invalid_input",
            )
        start_line = input_data.get("start_line")
        end_line = input_data.get("end_line")
        if start_line is not None and (not isinstance(start_line, int) or start_line < 1):
            raise ValidationError(
                "'start_line' must be a positive integer >= 1.", code="invalid_input"
            )
        if end_line is not None and (not isinstance(end_line, int) or end_line < 1):
            raise ValidationError(
                "'end_line' must be a positive integer >= 1.", code="invalid_input"
            )
        if start_line and end_line and start_line > end_line:
            raise ValidationError(
                "'start_line' cannot be greater than 'end_line'.",
                code="invalid_input",
            )
        return {"path": path, "start_line": start_line, "end_line": end_line}

    async def execute(
        self, context: ToolExecutionContext, input_data: dict[str, Any]
    ) -> ToolResult:
        if not context.repo_root:
            return ToolResult(
                success=False,
                output="No repository root directory available in execution context.",
                error="missing_repo_root",
            )

        try:
            validated = self.validate(input_data)
            target_path = safe_resolve_repo_path(context.repo_root, validated["path"])
        except ValidationError as exc:
            return ToolResult(success=False, output=exc.message, error=exc.code)

        if not target_path.exists() or not target_path.is_file():
            return ToolResult(
                success=False,
                output=f"File '{validated['path']}' not found.",
                error="file_not_found",
            )

        try:
            content = target_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return ToolResult(
                success=False,
                output=f"Failed to read file: {exc}",
                error="read_error",
            )

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)
        start = validated["start_line"] or 1
        end = validated["end_line"] or total_lines

        # Slice 1-indexed inclusive
        sliced_lines = lines[start - 1 : end]
        sliced_content = "".join(sliced_lines)
        sanitized = redact_secrets(sliced_content)

        return ToolResult(
            success=True,
            output=sanitized,
            data={
                "path": validated["path"],
                "total_lines": total_lines,
                "start_line": start,
                "end_line": end,
            },
        )


class RepositorySearchTool:
    """Tool: repository.search."""

    name = "repository.search"
    description = "Search text content across files in the repository."
    category = ToolCategory.REPOSITORY
    risk_level = RiskLevel.READ_ONLY
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Text query or pattern to search for in files",
            },
            "path_pattern": {
                "type": "string",
                "description": "Optional glob pattern to filter files (e.g. '*.py', 'src/*')",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of matching lines to return (default: 30)",
                "default": 30,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "matches": {"type": "array"},
            "total_matches": {"type": "integer"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data.get("query")
        if not query or not isinstance(query, str):
            raise ValidationError(
                "'query' is required and must be a non-empty string.",
                code="invalid_input",
            )
        path_pattern = input_data.get("path_pattern")
        limit = input_data.get("limit", 30)
        if not isinstance(limit, int) or limit <= 0:
            limit = 30
        return {
            "query": query,
            "path_pattern": path_pattern,
            "limit": min(limit, 100),
        }

    async def execute(
        self, context: ToolExecutionContext, input_data: dict[str, Any]
    ) -> ToolResult:
        if not context.repo_root:
            return ToolResult(
                success=False,
                output="No repository root directory available in execution context.",
                error="missing_repo_root",
            )

        validated = self.validate(input_data)
        query = validated["query"]
        pattern = validated["path_pattern"]
        limit = validated["limit"]

        repo_root = Path(context.repo_root).resolve()
        matches: list[dict[str, Any]] = []

        try:
            pattern_regex = re.compile(re.escape(query), re.IGNORECASE)
        except Exception:
            pattern_regex = re.compile(query, re.IGNORECASE)

        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):
                    continue
                file_path = Path(root) / fname
                try:
                    rel_path = file_path.relative_to(repo_root).as_posix()
                except ValueError:
                    continue

                if pattern and not fnmatch(rel_path, pattern):
                    continue

                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                for line_no, line in enumerate(text.splitlines(), start=1):
                    if pattern_regex.search(line):
                        matches.append({
                            "path": rel_path,
                            "line_number": line_no,
                            "line_content": redact_secrets(line.strip()),
                        })
                        if len(matches) >= limit:
                            break
                if len(matches) >= limit:
                    break
            if len(matches) >= limit:
                break

        if not matches:
            return ToolResult(
                success=True,
                output=f"No matches found for '{query}'.",
                data={"matches": [], "total_matches": 0},
            )

        formatted_lines = [
            f"{m['path']}:{m['line_number']}: {m['line_content']}"
            for m in matches
        ]
        return ToolResult(
            success=True,
            output=f"Found {len(matches)} matches:\n" + "\n".join(formatted_lines),
            data={"matches": matches, "total_matches": len(matches)},
        )


class CodeSearchSymbolTool:
    """Tool: code.search_symbol."""

    name = "code.search_symbol"
    description = "Search for function, class, or type symbol definitions in the repository."
    category = ToolCategory.CODE
    risk_level = RiskLevel.READ_ONLY
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Symbol name or substring to search for",
            },
            "kind": {
                "type": "string",
                "description": "Optional symbol kind (e.g. 'function', 'class', 'method')",
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array"},
            "total": {"type": "integer"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        name = input_data.get("name")
        if not name or not isinstance(name, str):
            raise ValidationError(
                "'name' is required and must be a non-empty string.",
                code="invalid_input",
            )
        return {"name": name, "kind": input_data.get("kind")}

    async def execute(
        self, context: ToolExecutionContext, input_data: dict[str, Any]
    ) -> ToolResult:
        if not context.repo_root:
            return ToolResult(
                success=False,
                output="No repository root directory available in execution context.",
                error="missing_repo_root",
            )

        validated = self.validate(input_data)
        query = validated["name"]
        kind_filter = (validated["kind"] or "").lower()

        repo_root = Path(context.repo_root).resolve()
        # Fast regex match for standard symbol definitions across common languages
        symbol_patterns = [
            # Python
            (re.compile(r"^\s*(def|class|async def)\s+([a-zA-Z0-9_]+)"), "python"),
            # TypeScript / JS
            (
                re.compile(
                    r"^\s*(function|class|interface|type|enum|const|let)\s+([a-zA-Z0-9_]+)"
                ),
                "ts/js",
            ),

            # Rust / Go
            (re.compile(r"^\s*(fn|struct|enum|type|func)\s+([a-zA-Z0-9_]+)"), "rust/go"),
        ]

        found: list[dict[str, Any]] = []

        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):
                    continue
                file_path = Path(root) / fname
                try:
                    rel_path = file_path.relative_to(repo_root).as_posix()
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                for line_no, line in enumerate(text.splitlines(), start=1):
                    for pat, _lang in symbol_patterns:
                        m = pat.match(line)
                        if m:
                            def_kind, sym_name = m.group(1), m.group(2)
                            if query.lower() in sym_name.lower():
                                if not kind_filter or kind_filter in def_kind.lower():
                                    found.append({
                                        "name": sym_name,
                                        "kind": def_kind,
                                        "path": rel_path,
                                        "line_number": line_no,
                                        "snippet": redact_secrets(line.strip()),
                                    })
                                    if len(found) >= 50:
                                        break
                    if len(found) >= 50:
                        break
            if len(found) >= 50:
                break

        if not found:
            return ToolResult(
                success=True,
                output=f"No symbols matching '{query}' found.",
                data={"symbols": [], "total": 0},
            )

        output_str = f"Found {len(found)} symbols:\n" + "\n".join(
            f"- {s['kind']} {s['name']} in {s['path']}:{s['line_number']}"
            for s in found
        )
        return ToolResult(
            success=True,
            output=output_str,
            data={"symbols": found, "total": len(found)},
        )


class CodeFindReferencesTool:
    """Tool: code.find_references."""

    name = "code.find_references"
    description = "Find references and usages of a symbol across the repository."
    category = ToolCategory.CODE
    risk_level = RiskLevel.READ_ONLY
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Symbol name to find references for",
            },
            "file_path": {
                "type": "string",
                "description": "Optional file path filter",
            },
        },
        "required": ["symbol"],
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "references": {"type": "array"},
            "total": {"type": "integer"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        symbol = input_data.get("symbol")
        if not symbol or not isinstance(symbol, str):
            raise ValidationError(
                "'symbol' is required and must be a non-empty string.",
                code="invalid_input",
            )
        return {"symbol": symbol, "file_path": input_data.get("file_path")}

    async def execute(
        self, context: ToolExecutionContext, input_data: dict[str, Any]
    ) -> ToolResult:
        if not context.repo_root:
            return ToolResult(
                success=False,
                output="No repository root directory available in execution context.",
                error="missing_repo_root",
            )

        validated = self.validate(input_data)
        symbol = validated["symbol"]
        file_filter = validated["file_path"]

        repo_root = Path(context.repo_root).resolve()
        word_boundary_regex = re.compile(rf"\b{re.escape(symbol)}\b")
        references: list[dict[str, Any]] = []

        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):
                    continue
                file_path = Path(root) / fname
                try:
                    rel_path = file_path.relative_to(repo_root).as_posix()
                except ValueError:
                    continue

                if file_filter and rel_path != file_filter and not fnmatch(rel_path, file_filter):
                    continue

                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                for line_no, line in enumerate(text.splitlines(), start=1):
                    if word_boundary_regex.search(line):
                        references.append({
                            "path": rel_path,
                            "line_number": line_no,
                            "snippet": redact_secrets(line.strip()),
                        })
                        if len(references) >= 50:
                            break
                if len(references) >= 50:
                    break
            if len(references) >= 50:
                break

        if not references:
            return ToolResult(
                success=True,
                output=f"No references to '{symbol}' found.",
                data={"references": [], "total": 0},
            )

        output_str = f"Found {len(references)} references to '{symbol}':\n" + "\n".join(
            f"- {r['path']}:{r['line_number']}: {r['snippet']}"
            for r in references
        )
        return ToolResult(
            success=True,
            output=output_str,
            data={"references": references, "total": len(references)},
        )
