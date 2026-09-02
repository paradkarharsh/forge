"""Unit tests for the application-layer ToolRegistry and default tool factory."""

import pytest

from forge_api.application.tools.tool_registry import ToolRegistry
from forge_api.domain.errors import ConflictError, NotFoundError
from forge_api.domain.tool import (
    RiskLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)
from forge_api.infrastructure.tools.default_registry import (
    create_default_tool_registry,
)


class DummyTool:
    def __init__(
        self,
        name: str = "dummy.tool",
        category: ToolCategory = ToolCategory.REPOSITORY,
        risk_level: RiskLevel = RiskLevel.READ_ONLY,
        enabled: bool = True,
    ) -> None:
        self._name = name
        self._category = category
        self._risk_level = risk_level
        self._enabled = enabled

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Dummy tool {self._name}"

    @property
    def category(self) -> ToolCategory:
        return self._category

    @property
    def risk_level(self) -> RiskLevel:
        return self._risk_level

    @property
    def input_schema(self) -> dict:
        return {"type": "object"}

    @property
    def output_schema(self) -> dict:
        return {"type": "object"}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def validate(self, input_data: dict) -> dict:
        return input_data

    async def execute(
        self, context: ToolExecutionContext, input_data: dict
    ) -> ToolResult:
        return ToolResult(success=True, output="dummy output")


class TestToolRegistry:
    def test_register_and_lookup(self) -> None:
        registry = ToolRegistry()
        tool = DummyTool("test.tool")
        registry.register(tool)

        assert registry.count() == 1
        assert registry.get("test.tool") is tool
        assert registry.require("test.tool") is tool

    def test_register_duplicate_raises_conflict(self) -> None:
        registry = ToolRegistry()
        tool1 = DummyTool("test.dup")
        tool2 = DummyTool("test.dup")

        registry.register(tool1)
        with pytest.raises(ConflictError) as exc_info:
            registry.register(tool2)
        assert exc_info.value.code == "tool_already_registered"

    def test_require_missing_tool_raises_not_found(self) -> None:
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None
        with pytest.raises(NotFoundError) as exc_info:
            registry.require("nonexistent")
        assert exc_info.value.code == "tool_not_found"

    def test_list_tools_filtering(self) -> None:
        registry = ToolRegistry()
        t1 = DummyTool("repo.tool", category=ToolCategory.REPOSITORY, enabled=True)
        t2 = DummyTool("file.tool", category=ToolCategory.FILE, enabled=True)
        t3 = DummyTool("file.disabled", category=ToolCategory.FILE, enabled=False)

        registry.register(t1)
        registry.register(t2)
        registry.register(t3)

        # All enabled
        all_enabled = registry.list_tools(enabled_only=True)
        assert len(all_enabled) == 2
        assert t3 not in all_enabled

        # All including disabled
        all_tools = registry.list_tools(enabled_only=False)
        assert len(all_tools) == 3

        # By category
        file_tools = registry.list_tools(category=ToolCategory.FILE, enabled_only=False)
        assert len(file_tools) == 2
        assert t1 not in file_tools

    def test_unregister(self) -> None:
        registry = ToolRegistry()
        tool = DummyTool("to.remove")
        registry.register(tool)
        assert registry.count() == 1

        assert registry.unregister("to.remove") is True
        assert registry.count() == 0
        assert registry.unregister("to.remove") is False

    def test_get_tool_specs(self) -> None:
        registry = ToolRegistry()
        tool = DummyTool(
            "spec.test",
            category=ToolCategory.CODE,
            risk_level=RiskLevel.LOW,
        )
        registry.register(tool)

        specs = registry.get_tool_specs()
        assert len(specs) == 1
        assert specs[0]["name"] == "spec.test"
        assert specs[0]["category"] == "code"
        assert specs[0]["risk_level"] == "low"
        assert specs[0]["parameters_schema"] == {"type": "object"}

    def test_default_tool_registry_initialization(self) -> None:
        registry = create_default_tool_registry()
        assert registry.count() == 12

        expected_tools = {
            "repository.list_files",
            "repository.read_file",
            "repository.search",
            "code.search_symbol",
            "code.find_references",
            "file.create",
            "file.modify",
            "file.delete",
            "git.status",
            "git.diff",
            "git.commit",
            "terminal.execute",
        }
        registered_names = {t.name for t in registry.list_tools(enabled_only=False)}
        assert registered_names == expected_tools
