"""Default tool registry factory for initializing the FP8 tool suite."""
from forge_api.application.tools.tool_registry import ToolRegistry
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
)


def create_default_tool_registry() -> ToolRegistry:
    """Create and populate a ToolRegistry with all standard FP8 development tools."""
    registry = ToolRegistry()

    # Repository & Code Read tools
    registry.register(RepositoryListFilesTool())
    registry.register(RepositoryReadFileTool())
    registry.register(RepositorySearchTool())
    registry.register(CodeSearchSymbolTool())
    registry.register(CodeFindReferencesTool())

    # Controlled File Write tools
    registry.register(FileCreateTool())
    registry.register(FileModifyTool())
    registry.register(FileDeleteTool())

    # Git tools
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitCommitTool())

    # Restricted Terminal Executor tool
    registry.register(TerminalExecuteTool())

    return registry
