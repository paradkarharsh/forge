"""Git reading and commit tools for FP8."""
import asyncio
import logging
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


async def _run_git(repo_dir: str, args: list[str], timeout: float = 30.0) -> tuple[int, str, str]:
    """Safely execute a git command inside the specified repo directory."""
    cmd = ["git", "-c", "core.quotepath=false", "--no-pager", "-C", repo_dir] + args
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")
        return (proc.returncode or 0), stdout_str, stderr_str
    except TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return 1, "", "git command timed out after 30 seconds"
    except Exception as exc:
        return 1, "", f"Failed to execute git: {exc}"


class GitStatusTool:
    """Tool: git.status."""

    name = "git.status"
    description = "Get working tree status (untracked, modified, and staged files)."
    category = ToolCategory.GIT
    risk_level = RiskLevel.READ_ONLY
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "is_clean": {"type": "boolean"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def execute(
        self, context: ToolExecutionContext, input_data: dict[str, Any]
    ) -> ToolResult:
        if not context.repo_root:
            return ToolResult(
                success=False,
                output="No repository root directory available in execution context.",
                error="missing_repo_root",
            )

        code, stdout, stderr = await _run_git(context.repo_root, ["status", "--porcelain"])
        if code != 0:
            return ToolResult(
                success=False,
                output=f"git status failed: {stderr.strip()}",
                error="git_error",
            )

        trimmed = stdout.strip()
        is_clean = len(trimmed) == 0
        output_text = "Working tree is clean." if is_clean else f"Git status:\n{trimmed}"

        return ToolResult(
            success=True,
            output=output_text,
            data={"status": trimmed, "is_clean": is_clean},
        )


class GitDiffTool:
    """Tool: git.diff."""

    name = "git.diff"
    description = "Get working tree or staged unified diffs."
    category = ToolCategory.GIT
    risk_level = RiskLevel.READ_ONLY
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional repository-relative path to inspect",
            },
            "staged": {
                "type": "boolean",
                "description": "Whether to inspect staged changes (default: False)",
                "default": False,
            },
        },
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "diff": {"type": "string"},
            "has_changes": {"type": "boolean"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        path = input_data.get("path")
        if path is not None and not isinstance(path, str):
            raise ValidationError("'path' must be a string.", code="invalid_input")
        staged = bool(input_data.get("staged", False))
        return {"path": path, "staged": staged}

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
        path = validated["path"]
        staged = validated["staged"]

        args = ["diff"]
        if staged:
            args.append("--staged")
        if path:
            try:
                target = safe_resolve_repo_path(context.repo_root, path)
                rel = target.relative_to(Path(context.repo_root).resolve()).as_posix()
                args.extend(["--", rel])
            except ValidationError as exc:
                return ToolResult(success=False, output=exc.message, error=exc.code)

        code, stdout, stderr = await _run_git(context.repo_root, args)
        if code != 0:
            return ToolResult(
                success=False,
                output=f"git diff failed: {stderr.strip()}",
                error="git_error",
            )

        diff_sanitized = redact_secrets(stdout)
        has_changes = len(diff_sanitized.strip()) > 0
        output_text = (
            diff_sanitized if has_changes else "No differences found (working tree clean)."
        )

        return ToolResult(
            success=True,
            output=output_text,
            data={"diff": diff_sanitized, "has_changes": has_changes},
        )


class GitCommitTool:
    """Tool: git.commit."""

    name = "git.commit"
    description = "Stage all modified files and create a git commit in the repository."
    category = ToolCategory.GIT
    risk_level = RiskLevel.HIGH
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Meaningful git commit message",
            },
        },
        "required": ["message"],
        "additionalProperties": False,
    }

    output_schema = {
        "type": "object",
        "properties": {
            "commit_hash": {"type": "string"},
            "message": {"type": "string"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        message = input_data.get("message")
        if not message or not isinstance(message, str) or not message.strip():
            raise ValidationError(
                "'message' is required and must be a non-empty string.",
                code="invalid_input",
            )
        return {"message": message.strip()}

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
        message = validated["message"]

        # 1. Stage all changes
        add_code, _, add_err = await _run_git(context.repo_root, ["add", "-A"])
        if add_code != 0:
            return ToolResult(
                success=False,
                output=f"Failed to stage changes: {add_err.strip()}",
                error="git_error",
            )

        # 2. Check if there are staged changes
        diff_code, diff_out, _ = await _run_git(
            context.repo_root, ["diff", "--cached", "--name-only"]
        )
        if diff_code == 0 and not diff_out.strip():

            return ToolResult(
                success=False,
                output="No changes staged to commit (working tree clean).",
                error="nothing_to_commit",
            )

        # 3. Create commit
        commit_code, commit_out, commit_err = await _run_git(
            context.repo_root, ["commit", "-m", message]
        )
        if commit_code != 0:
            return ToolResult(
                success=False,
                output=f"git commit failed: {commit_err.strip() or commit_out.strip()}",
                error="git_error",
            )

        # 4. Resolve new commit hash
        rev_code, rev_out, _ = await _run_git(context.repo_root, ["rev-parse", "HEAD"])
        commit_hash = rev_out.strip() if rev_code == 0 else "unknown"

        return ToolResult(
            success=True,
            output=f"Successfully committed changes ({commit_hash[:8]}): {message}",
            data={"commit_hash": commit_hash, "message": message},
        )
