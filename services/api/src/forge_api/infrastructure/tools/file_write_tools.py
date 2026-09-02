"""Controlled file writing, modification, and deletion tools for FP8."""
import difflib
import logging
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


def _generate_diff(
    rel_path: str, old_content: str, new_content: str
) -> str:
    """Generate a clean unified diff between old and new text contents."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{rel_path}",
        tofile=f"b/{rel_path}",
    )
    diff_str = "".join(diff)
    return redact_secrets(diff_str)


class FileCreateTool:
    """Tool: file.create."""

    name = "file.create"
    description = "Create a new file in the repository with the specified content."
    category = ToolCategory.FILE
    risk_level = RiskLevel.MEDIUM
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository-relative path of the file to create",
            },
            "content": {
                "type": "string",
                "description": "Full text content of the file",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite if file already exists (default: False)",
                "default": False,
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "bytes_written": {"type": "integer"},
            "diff": {"type": "string"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        path = input_data.get("path")
        if not path or not isinstance(path, str):
            raise ValidationError(
                "'path' is required and must be a non-empty string.",
                code="invalid_input",
            )
        content = input_data.get("content")
        if content is None or not isinstance(content, str):
            raise ValidationError(
                "'content' is required and must be a string.",
                code="invalid_input",
            )
        overwrite = bool(input_data.get("overwrite", False))
        return {"path": path, "content": content, "overwrite": overwrite}

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

        rel_path = validated["path"]
        content = validated["content"]
        overwrite = validated["overwrite"]

        if target_path.exists() and not overwrite:
            return ToolResult(
                success=False,
                output=f"File '{rel_path}' already exists. Set overwrite=True to overwrite.",
                error="file_exists",
            )

        old_content = ""
        if target_path.exists():
            old_content = target_path.read_text(encoding="utf-8", errors="replace")

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(
                success=False,
                output=f"Failed to write file '{rel_path}': {exc}",
                error="write_error",
            )

        diff = _generate_diff(rel_path, old_content, content)
        output_msg = f"Created file '{rel_path}' ({len(content)} characters).\n"
        if diff:
            output_msg += f"Diff:\n{diff}"

        return ToolResult(
            success=True,
            output=output_msg,
            data={
                "path": rel_path,
                "bytes_written": len(content.encode("utf-8")),
                "diff": diff,
            },
        )


class FileModifyTool:
    """Tool: file.modify."""

    name = "file.modify"
    description = "Modify an existing file in the repository with new content."
    category = ToolCategory.FILE
    risk_level = RiskLevel.MEDIUM
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository-relative path of the file to modify",
            },
            "content": {
                "type": "string",
                "description": "Complete replacement content for the file",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "bytes_written": {"type": "integer"},
            "diff": {"type": "string"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        path = input_data.get("path")
        if not path or not isinstance(path, str):
            raise ValidationError(
                "'path' is required and must be a non-empty string.",
                code="invalid_input",
            )
        content = input_data.get("content")
        if content is None or not isinstance(content, str):
            raise ValidationError(
                "'content' is required and must be a string.",
                code="invalid_input",
            )
        return {"path": path, "content": content}

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

        rel_path = validated["path"]
        content = validated["content"]

        if not target_path.exists() or not target_path.is_file():
            return ToolResult(
                success=False,
                output=f"File '{rel_path}' not found.",
                error="file_not_found",
            )

        try:
            old_content = target_path.read_text(encoding="utf-8", errors="replace")
            target_path.write_text(content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(
                success=False,
                output=f"Failed to modify file '{rel_path}': {exc}",
                error="write_error",
            )

        diff = _generate_diff(rel_path, old_content, content)
        output_msg = f"Modified file '{rel_path}'.\n"
        if diff:
            output_msg += f"Diff:\n{diff}"
        else:
            output_msg += "No changes detected."

        return ToolResult(
            success=True,
            output=output_msg,
            data={
                "path": rel_path,
                "bytes_written": len(content.encode("utf-8")),
                "diff": diff,
            },
        )


class FileDeleteTool:
    """Tool: file.delete."""

    name = "file.delete"
    description = "Delete a file from the repository."
    category = ToolCategory.FILE
    risk_level = RiskLevel.MEDIUM
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository-relative path of the file to delete",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "diff": {"type": "string"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        path = input_data.get("path")
        if not path or not isinstance(path, str):
            raise ValidationError(
                "'path' is required and must be a non-empty string.",
                code="invalid_input",
            )
        return {"path": path}

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

        rel_path = validated["path"]

        if not target_path.exists() or not target_path.is_file():
            return ToolResult(
                success=False,
                output=f"File '{rel_path}' not found.",
                error="file_not_found",
            )

        try:
            old_content = target_path.read_text(encoding="utf-8", errors="replace")
            target_path.unlink()
        except Exception as exc:
            return ToolResult(
                success=False,
                output=f"Failed to delete file '{rel_path}': {exc}",
                error="delete_error",
            )

        diff = _generate_diff(rel_path, old_content, "")
        output_msg = f"Deleted file '{rel_path}'.\n"
        if diff:
            output_msg += f"Diff:\n{diff}"

        return ToolResult(
            success=True,
            output=output_msg,
            data={"path": rel_path, "diff": diff},
        )
