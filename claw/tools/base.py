"""工具基类与注册表。

每个工具用 pydantic 模型声明参数, 由此自动生成 OpenAI function-calling 的
JSON schema, 避免手写易错的 schema。
"""

from __future__ import annotations

import abc
from typing import Any

from pydantic import BaseModel


class Tool(abc.ABC):
    """所有工具的抽象基类。"""

    name: str
    description: str
    args_model: type[BaseModel]
    # 是否为有副作用的操作(写文件 / 执行命令), 用于 safety 判定是否需确认
    mutating: bool = False

    @abc.abstractmethod
    def run(self, **kwargs: Any) -> str:
        """执行工具并返回字符串结果。"""

    def to_schema(self) -> dict[str, Any]:
        """生成 function-calling schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }

    def preview(self, **kwargs: Any) -> str:
        """返回给用户确认时展示的简短描述。"""
        args = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        return f"{self.name}({args})"


class ToolRegistry:
    """工具注册表: 管理工具集合并提供调度。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具重名: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]
