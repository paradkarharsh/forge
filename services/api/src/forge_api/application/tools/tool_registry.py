"""Tool registry for discovering and managing provider-agnostic agent tools."""
import logging
from typing import Any

from forge_api.domain.errors import ConflictError, NotFoundError
from forge_api.domain.tool import Tool, ToolCategory

logger = logging.getLogger(__name__)


class ToolRegistry:
    """In-memory registry of tools available to the AI agent orchestrator."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance. Rejects duplicate registrations."""
        if tool.name in self._tools:
            raise ConflictError(
                f"Tool '{tool.name}' is already registered.",
                code="tool_already_registered",
            )
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s (category: %s)", tool.name, tool.category)

    def get(self, name: str) -> Tool | None:
        """Retrieve a tool by name, or None if not registered."""
        return self._tools.get(name)

    def require(self, name: str) -> Tool:
        """Retrieve a tool by name or raise NotFoundError."""
        tool = self.get(name)
        if not tool:
            raise NotFoundError(
                f"Tool '{name}' not found in registry.",
                code="tool_not_found",
            )
        return tool

    def list_tools(
        self,
        category: ToolCategory | None = None,
        enabled_only: bool = True,
    ) -> list[Tool]:
        """List registered tools with optional category and enabled filtering."""
        tools = list(self._tools.values())
        if category is not None:
            tools = [t for t in tools if t.category == category]
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def unregister(self, name: str) -> bool:
        """Remove a tool by name. Returns True if removed, False if not found."""
        return self._tools.pop(name, None) is not None

    def get_tool_specs(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        """Return provider-neutral tool schemas suitable for LLM prompt construction."""
        tools = self.list_tools(enabled_only=enabled_only)
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
                "risk_level": t.risk_level.value,
                "parameters_schema": t.input_schema,
            }
            for t in tools
        ]

    def count(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)
