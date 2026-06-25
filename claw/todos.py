"""任务清单(TODO)状态: 供 agent 规划多步任务时维护与展示。"""

from __future__ import annotations

from dataclasses import dataclass

VALID_STATUS = ("pending", "in_progress", "completed", "cancelled")

_STATUS_MARK = {
    "pending": "[ ]",
    "in_progress": "[~]",
    "completed": "[x]",
    "cancelled": "[/]",
}


@dataclass
class TodoItem:
    """单个任务项。"""

    id: str
    content: str
    status: str = "pending"

    def normalized_status(self) -> str:
        return self.status if self.status in VALID_STATUS else "pending"


class TodoStore:
    """保存当前任务清单, 支持整体替换与按 id 合并。"""

    def __init__(self) -> None:
        self._items: list[TodoItem] = []

    @property
    def items(self) -> list[TodoItem]:
        return self._items

    def set(self, items: list[TodoItem], merge: bool = False) -> None:
        if not merge:
            self._items = list(items)
            return
        index = {item.id: item for item in self._items}
        order = [item.id for item in self._items]
        for item in items:
            if item.id not in index:
                order.append(item.id)
            index[item.id] = item
        self._items = [index[i] for i in order]

    def clear(self) -> None:
        self._items = []

    def render(self) -> str:
        """渲染成带勾选框的纯文本清单。"""
        if not self._items:
            return "(任务清单为空)"
        lines = []
        for item in self._items:
            mark = _STATUS_MARK.get(item.normalized_status(), "[ ]")
            lines.append(f"{mark} {item.content}")
        return "\n".join(lines)

    def summary(self) -> str:
        """统计各状态数量, 供日志/状态栏使用。"""
        total = len(self._items)
        done = sum(1 for i in self._items if i.normalized_status() == "completed")
        return f"任务进度: {done}/{total} 已完成"
