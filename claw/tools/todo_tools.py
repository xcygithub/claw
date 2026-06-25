"""任务规划工具: 让 agent 维护一份可见的多步任务清单。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from claw.todos import TodoItem, TodoStore
from claw.tools.base import Tool


class TodoItemArg(BaseModel):
    id: str = Field(description="任务项唯一标识(短横线分隔的英文短语即可)")
    content: str = Field(description="任务描述")
    status: Literal["pending", "in_progress", "completed", "cancelled"] = Field(
        default="pending", description="任务状态"
    )


class WriteTodosArgs(BaseModel):
    todos: list[TodoItemArg] = Field(description="完整的任务项列表")
    merge: bool = Field(
        default=False,
        description="True 则按 id 合并更新已有项(只改状态时用); False 则整体替换",
    )


class WriteTodosTool(Tool):
    name = "write_todos"
    description = (
        "创建或更新当前任务清单, 用于规划与跟踪多步任务。"
        "遇到需要 3 步以上的复杂任务时, 先用本工具列出计划; "
        "推进过程中再次调用以更新状态(同一时间只保持一个 in_progress)。"
        "简单的一两步任务无需使用。"
    )
    args_model = WriteTodosArgs
    mutating = False

    def __init__(self, store: TodoStore) -> None:
        self.store = store

    def run(
        self,
        todos: list[dict[str, Any]] | None = None,
        merge: bool = False,
    ) -> str:
        items = [
            TodoItem(
                id=str(t.get("id", "")),
                content=str(t.get("content", "")),
                status=str(t.get("status", "pending")),
            )
            for t in (todos or [])
        ]
        self.store.set(items, merge=merge)
        return "任务清单已更新:\n" + self.store.render()

    def preview(self, todos: list[dict[str, Any]] | None = None, merge: bool = False) -> str:
        count = len(todos or [])
        action = "合并更新" if merge else "更新"
        return f"{action}任务清单 ({count} 项)"
