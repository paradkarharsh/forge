"""Restricted terminal executor for allowlisted development commands."""
import asyncio
import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any

from forge_api.domain.errors import ValidationError
from forge_api.domain.tool import (
    RiskLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
    redact_secrets,
)

logger = logging.getLogger(__name__)

_MAX_OUTPUT_BYTES = 65_536  # 64KB
_TIMEOUT_SECONDS = 30.0

# Disallowed shell chaining, redirection, or expansion characters
_FORBIDDEN_CHARS_PATTERN = re.compile(r"[;&|><`$\n\r\t]")

_FORBIDDEN_COMMANDS = frozenset({
    "bash",
    "sh",
    "zsh",
    "csh",
    "ksh",
    "fish",
    "powershell",
    "pwsh",
    "cmd",
    "command",
    "curl",
    "wget",
    "nc",
    "netcat",
    "ssh",
    "scp",
    "sftp",
    "ftp",
    "telnet",
    "nmap",
    "sudo",
    "su",
    "doas",
    "chmod",
    "chown",
    "chgrp",
    "useradd",
    "usermod",
    "userdel",
    "kill",
    "pkill",
    "killall",
    "taskkill",
    "rm",
    "del",
    "erase",
    "env",
    "printenv",
    "export",
    "set",
    "alias",
})


def _sanitize_environment() -> dict[str, str]:
    """Create a minimal sanitized environment omitting secrets and Forge config."""
    safe_keys = {
        "PATH",
        "HOME",
        "USERPROFILE",
        "LANG",
        "LC_ALL",
        "TEMP",
        "TMP",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "NODE_ENV",
        "PYTHONPATH",
        "TERM",
    }
    sanitized = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}

    # Scrub any key that might carry sensitive data
    for k in list(sanitized.keys()):
        upper_k = k.upper()
        if (
            upper_k.startswith("FORGE_")
            or "DATABASE" in upper_k
            or "REDIS" in upper_k
            or "SECRET" in upper_k
            or "PASSWORD" in upper_k
            or "TOKEN" in upper_k
            or "API_KEY" in upper_k
            or "JWT" in upper_k
        ):
            del sanitized[k]

    return sanitized


def validate_terminal_command(command: str) -> list[str]:
    """Validate that the command string is allowlisted and free of shell injection."""
    if not command or not isinstance(command, str) or not command.strip():
        raise ValidationError("Command must not be empty.", code="invalid_command")

    # Reject dangerous shell chaining / redirection characters
    if _FORBIDDEN_CHARS_PATTERN.search(command):
        raise ValidationError(
            "Command chaining, pipes, redirection, and shell variables are forbidden.",
            code="forbidden_command_syntax",
        )

    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise ValidationError(
            f"Malformed command line syntax: {exc}", code="invalid_command"
        ) from None

    if not argv:
        raise ValidationError("Command must not be empty.", code="invalid_command")

    binary = Path(argv[0]).name.lower()
    # Strip .exe on Windows if present
    if binary.endswith(".exe"):
        binary = binary[:-4]

    # Explicit check for forbidden commands
    if binary in _FORBIDDEN_COMMANDS:
        raise ValidationError(
            f"Execution of '{binary}' is forbidden for security.",
            code="forbidden_command",
        )

    # ─── Allowlist Rules ───────────────────────────────────────────────

    # 1. pytest
    if binary == "pytest":
        return argv

    # 2. ruff
    if binary == "ruff":
        if len(argv) >= 2 and argv[1] in ("check", "format"):
            return argv
        raise ValidationError(
            "Only 'ruff check' and 'ruff format' subcommands are permitted.",
            code="command_not_allowlisted",
        )

    # 3. tsc
    if binary == "tsc":
        if "--noEmit" in argv or "-p" in argv:
            return argv
        raise ValidationError(
            "'tsc' execution must include '--noEmit'.",
            code="command_not_allowlisted",
        )

    # 4. cargo
    if binary == "cargo":
        if len(argv) >= 2 and argv[1] in ("test", "check", "clippy"):
            return argv
        raise ValidationError(
            "Only 'cargo test', 'cargo check', and 'cargo clippy' subcommands are permitted.",
            code="command_not_allowlisted",
        )

    # 5. npm
    if binary == "npm":
        if len(argv) >= 2 and (
            argv[1] in ("test", "t")
            or (
                argv[1] == "run"
                and len(argv) >= 3
                and argv[2] in ("test", "lint", "check", "typecheck", "build")
            )
        ):
            return argv
        raise ValidationError(
            "Only 'npm test' and safe 'npm run "
            "(test|lint|check|typecheck|build)' subcommands are permitted.",
            code="command_not_allowlisted",
        )

    # 6. git (read-only inspect status/diff)
    if binary == "git":
        if len(argv) >= 2 and argv[1] in ("status", "diff"):
            return argv
        raise ValidationError(
            "Terminal execution of git is limited to 'git status' and 'git diff'. "
            "Use dedicated git tools for other actions.",
            code="command_not_allowlisted",
        )

    # 7. python / python3 module execution
    if binary in ("python", "python3", "py"):
        if len(argv) >= 3 and argv[1] == "-m" and argv[2] in ("pytest", "unittest", "ruff"):
            return argv
        raise ValidationError(
            "Python terminal execution is limited to '-m pytest', '-m unittest', or '-m ruff'.",
            code="command_not_allowlisted",
        )

    raise ValidationError(
        f"Command '{binary}' is not in the allowlist of approved development commands.",
        code="command_not_allowlisted",
    )


class TerminalExecuteTool:
    """Tool: terminal.execute."""

    name = "terminal.execute"
    description = (
        "Execute an allowlisted, non-interactive development command "
        "(e.g. pytest, npm test, ruff check) inside the repository."
    )
    category = ToolCategory.TERMINAL
    risk_level = RiskLevel.HIGH
    enabled = True

    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": (
                    "The allowlisted command string to execute "
                    "(e.g. 'pytest tests/test_app.py', 'npm test')"
                ),
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }


    output_schema = {
        "type": "object",
        "properties": {
            "exit_code": {"type": "integer"},
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "command": {"type": "string"},
        },
    }

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        command = input_data.get("command")
        if not command or not isinstance(command, str):
            raise ValidationError(
                "'command' is required and must be a non-empty string.",
                code="invalid_input",
            )
        # Verify allowlist syntax
        argv = validate_terminal_command(command)
        return {"command": command.strip(), "argv": argv}

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
        except ValidationError as exc:
            return ToolResult(success=False, output=exc.message, error=exc.code)

        argv = validated["argv"]
        repo_root = str(Path(context.repo_root).resolve())
        env = _sanitize_environment()
        timeout = min(context.timeout_seconds, _TIMEOUT_SECONDS)

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=repo_root,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            exit_code = proc.returncode or 0
        except TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return ToolResult(
                success=False,
                output=f"Command '{validated['command']}' timed out after {timeout} seconds.",
                error="timeout",
                data={"exit_code": -1, "command": validated["command"]},
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output=f"Failed to execute command '{validated['command']}': {exc}",
                error="execution_error",
                data={"exit_code": -1, "command": validated["command"]},
            )

        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")

        # Combine and cap output to 64KB
        combined = stdout_str
        if stderr_str:
            combined = f"{stdout_str}\n[stderr]:\n{stderr_str}" if combined else stderr_str

        combined_bytes = combined.encode("utf-8")
        if len(combined_bytes) > _MAX_OUTPUT_BYTES:
            truncated_text = combined_bytes[:_MAX_OUTPUT_BYTES].decode(
                "utf-8", errors="ignore"
            )
            combined = (
                f"{truncated_text}\n\n[... Output truncated: "
                f"exceeded {_MAX_OUTPUT_BYTES} byte limit ...]"
            )

        sanitized_output = redact_secrets(combined)
        fallback_msg = f"Command completed with exit code {exit_code}."

        return ToolResult(
            success=(exit_code == 0),
            output=sanitized_output if sanitized_output else fallback_msg,
            data={

                "exit_code": exit_code,
                "command": validated["command"],
                "stdout": redact_secrets(stdout_str),
                "stderr": redact_secrets(stderr_str),
            },
        )
