"""内置工具集合。"""

from __future__ import annotations

from claw.memory_store import MemoryStore
from claw.todos import TodoStore
from claw.tools.base import Tool, ToolRegistry
from claw.tools.file_tools import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from claw.tools.memory_tools import SearchMemoryTool, UpdateMemoryTool
from claw.tools.search_tools import GlobTool, GrepTool
from claw.tools.shell_tools import RunCommandTool
from claw.tools.todo_tools import WriteTodosTool


def build_default_registry(
    memory_store: MemoryStore,
    todo_store: TodoStore | None = None,
) -> ToolRegistry:
    """构造默认工具注册表。"""
    registry = ToolRegistry()
    registry.register(WriteTodosTool(store=todo_store or TodoStore()))
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(ListDirTool())
    registry.register(GrepTool())
    registry.register(GlobTool())
    registry.register(RunCommandTool())
    registry.register(UpdateMemoryTool(memory_store=memory_store))
    registry.register(SearchMemoryTool(memory_store=memory_store))
    return registry


__all__ = ["Tool", "ToolRegistry", "build_default_registry"]
