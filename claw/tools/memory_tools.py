"""记忆相关工具: 让 agent 主动读写结构化记忆(项目记忆 CLAW.md / 全局记忆 GLOBAL.md)。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from claw.memory_store import MemoryStore
from claw.tools.base import Tool


class UpdateMemoryArgs(BaseModel):
    content: str = Field(description="要记录的内容(项目约定/技术栈/常用命令/重要决策等)")
    section: str | None = Field(
        default=None, description="归属的小节标题, 留空则归入默认区"
    )
    tags: list[str] | None = Field(
        default=None, description="标签列表, 便于后续用 search_memory 检索"
    )
    importance: str = Field(
        default="normal", description="重要性: low / normal / high"
    )
    scope: str = Field(
        default="project",
        description=(
            "记忆范围: project(当前项目, 默认, 写入 CLAW.md) 或 "
            "global(跨项目的个人偏好/常用命令, 写入 GLOBAL.md)"
        ),
    )


class UpdateMemoryTool(Tool):
    name = "update_memory"
    description = (
        "把对项目长期有用的信息写入结构化记忆(项目记忆 CLAW.md 或全局记忆 GLOBAL.md), "
        "下次会话会自动加载摘要, 内容较多时也可被 search_memory 检索到。"
        "适合记录: 项目约定、构建/测试命令、架构决策、易错点、个人偏好。不要记录临时性内容。"
    )
    args_model = UpdateMemoryArgs
    mutating = True

    def __init__(self, memory_store: MemoryStore) -> None:
        self.memory_store = memory_store

    def run(
        self,
        content: str,
        section: str | None = None,
        tags: list[str] | None = None,
        importance: str = "normal",
        scope: str = "project",
    ) -> str:
        scope = scope if scope in ("project", "global") else "project"
        try:
            entry = self.memory_store.add(
                content=content,
                section=section,
                tags=tags,
                importance=importance,
                scope=scope,
                source="manual",
            )
        except Exception as exc:  # noqa: BLE001
            return f"错误: 无法写入记忆: {exc}"
        label = "全局记忆 GLOBAL.md" if scope == "global" else "项目记忆 CLAW.md"
        return f"已记录到{label} [{entry.section}] (id={entry.id})"

    def preview(
        self,
        content: str = "",
        section: str | None = None,
        tags: list[str] | None = None,
        importance: str = "normal",
        scope: str = "project",
    ) -> str:
        snippet = content.strip().replace("\n", " ")
        if len(snippet) > 60:
            snippet = snippet[:60] + "..."
        label = "全局记忆 GLOBAL.md" if scope == "global" else "项目记忆 CLAW.md"
        return f"写入{label}: {snippet}"


class SearchMemoryArgs(BaseModel):
    query: str = Field(description="检索关键词, 支持多个词用空格分隔")
    scope: str | None = Field(
        default=None, description="限定范围: project / global, 留空则两者都搜"
    )
    top_k: int = Field(default=8, description="最多返回条数")


class SearchMemoryTool(Tool):
    name = "search_memory"
    description = (
        "按关键词检索项目记忆(CLAW.md)与全局记忆(GLOBAL.md)的全部条目, 用于查找系统提示词"
        "摘要里没有展示的更早、更细节的记忆; 记忆较多、摘要提示有省略时应使用本工具。"
    )
    args_model = SearchMemoryArgs
    mutating = False

    def __init__(self, memory_store: MemoryStore) -> None:
        self.memory_store = memory_store

    def run(self, query: str, scope: str | None = None, top_k: int = 8) -> str:
        scope = scope if scope in ("project", "global") else None
        results = self.memory_store.search(query, scope=scope, top_k=top_k)
        if not results:
            return "未找到匹配的记忆条目。"
        lines = []
        for entry in results:
            scope_label = "全局" if entry.scope == "global" else "项目"
            tag_str = f" #{' #'.join(entry.tags)}" if entry.tags else ""
            lines.append(
                f"- [{scope_label}/{entry.section}] (id={entry.id}){tag_str} {entry.content}"
            )
        return "\n".join(lines)

    def preview(self, query: str = "", scope: str | None = None, top_k: int = 8) -> str:
        return f"检索记忆: {query}"
