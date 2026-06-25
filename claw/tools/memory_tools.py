"""记忆相关工具: 让 agent 主动把经验写入项目记忆文件 CLAW.md。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from claw.tools.base import Tool


class UpdateMemoryArgs(BaseModel):
    content: str = Field(description="要记录的内容(项目约定/技术栈/常用命令/重要决策等)")
    section: str | None = Field(
        default=None, description="归属的小节标题, 留空则追加到默认区"
    )


class UpdateMemoryTool(Tool):
    name = "update_memory"
    description = (
        "把对项目长期有用的信息写入项目记忆文件(CLAW.md), 下次会话会自动加载。"
        "适合记录: 项目约定、构建/测试命令、架构决策、易错点。不要记录临时性内容。"
    )
    args_model = UpdateMemoryArgs
    mutating = True

    def __init__(self, memory_path: str) -> None:
        self.memory_path = Path(memory_path)

    def run(self, content: str, section: str | None = None) -> str:
        try:
            existing = (
                self.memory_path.read_text(encoding="utf-8")
                if self.memory_path.exists()
                else "# 项目记忆 (CLAW.md)\n\n由 Claw 维护, 记录跨会话的长期项目知识。\n"
            )
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            heading = f"\n## {section}\n" if section else ""
            entry = f"{heading}\n- ({stamp}) {content.strip()}\n"
            self.memory_path.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return f"错误: 无法写入记忆文件: {exc}"
        return f"已记录到 {self.memory_path.name}"

    def preview(self, content: str = "", section: str | None = None) -> str:
        snippet = content.strip().replace("\n", " ")
        if len(snippet) > 60:
            snippet = snippet[:60] + "..."
        return f"写入记忆 CLAW.md: {snippet}"
