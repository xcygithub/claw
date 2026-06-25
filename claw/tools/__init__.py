"""内置工具集合。"""

from __future__ import annotations

from claw.tools.base import Tool, ToolRegistry
from claw.tools.file_tools import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from claw.tools.memory_tools import UpdateMemoryTool
from claw.tools.search_tools import GlobTool, GrepTool
from claw.tools.shell_tools import RunCommandTool


def build_default_registry(memory_path: str) -> ToolRegistry:
    """构造默认工具注册表。"""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(ListDirTool())
    registry.register(GrepTool())
    registry.register(GlobTool())
    registry.register(RunCommandTool())
    registry.register(UpdateMemoryTool(memory_path=memory_path))
    return registry


__all__ = ["Tool", "ToolRegistry", "build_default_registry"]
