"""文件相关工具: 读取 / 写入 / 编辑 / 列目录。"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from claw.tools.base import Tool


class ReadFileArgs(BaseModel):
    path: str = Field(description="要读取的文件路径(相对或绝对)")
    offset: int = Field(default=1, description="起始行号(从 1 开始)")
    limit: int | None = Field(default=None, description="读取的最大行数, 留空读到结尾")


class ReadFileTool(Tool):
    name = "read_file"
    description = "读取文本文件内容, 返回带行号的文本。可用 offset/limit 读取大文件的片段。"
    args_model = ReadFileArgs

    def run(self, path: str, offset: int = 1, limit: int | None = None) -> str:
        p = Path(path)
        if not p.exists():
            return f"错误: 文件不存在: {path}"
        if p.is_dir():
            return f"错误: 这是目录而非文件: {path}"
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as exc:  # noqa: BLE001
            return f"错误: 无法读取文件: {exc}"

        start = max(offset - 1, 0)
        end = len(lines) if limit is None else min(start + limit, len(lines))
        selected = lines[start:end]
        if not selected:
            return "(文件为空或指定范围无内容)"
        width = len(str(end))
        numbered = "\n".join(
            f"{str(i + start + 1).rjust(width)}|{line}"
            for i, line in enumerate(selected)
        )
        return numbered


class WriteFileArgs(BaseModel):
    path: str = Field(description="要写入的文件路径")
    content: str = Field(description="完整的文件内容")


class WriteFileTool(Tool):
    name = "write_file"
    description = "创建新文件或用给定内容完整覆盖已有文件。父目录不存在时会自动创建。"
    args_model = WriteFileArgs
    mutating = True

    def run(self, path: str, content: str) -> str:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            existed = p.exists()
            p.write_text(content, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return f"错误: 无法写入文件: {exc}"
        action = "覆盖" if existed else "创建"
        return f"已{action}文件: {path} ({len(content)} 字符)"

    def preview(self, path: str = "", content: str = "") -> str:
        lines = content.count("\n") + 1 if content else 0
        return f"写入文件 {path} ({lines} 行, {len(content)} 字符)"


class EditFileArgs(BaseModel):
    path: str = Field(description="要编辑的文件路径")
    old_string: str = Field(description="要被替换的原文本(需在文件中唯一)")
    new_string: str = Field(description="替换后的新文本")
    replace_all: bool = Field(default=False, description="是否替换所有匹配项")


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "对文件做精确字符串替换。old_string 必须与文件内容完全一致; "
        "若不唯一且未设置 replace_all 会报错。请包含足够上下文保证唯一。"
    )
    args_model = EditFileArgs
    mutating = True

    def run(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        p = Path(path)
        if not p.exists():
            return f"错误: 文件不存在: {path}"
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return f"错误: 无法读取文件: {exc}"

        count = text.count(old_string)
        if count == 0:
            return "错误: 未找到匹配的 old_string, 请确认文本完全一致(含缩进)。"
        if count > 1 and not replace_all:
            return (
                f"错误: old_string 匹配到 {count} 处, 不唯一。"
                "请增加上下文使其唯一, 或设置 replace_all=true。"
            )
        new_text = text.replace(old_string, new_string)
        try:
            p.write_text(new_text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return f"错误: 无法写入文件: {exc}"
        return f"已编辑 {path} (替换 {count if replace_all else 1} 处)"

    def preview(self, path: str = "", old_string: str = "", new_string: str = "", replace_all: bool = False) -> str:
        return f"编辑文件 {path} (替换 {'全部' if replace_all else '1'} 处)"


class ListDirArgs(BaseModel):
    path: str = Field(default=".", description="要列出的目录路径")


class ListDirTool(Tool):
    name = "list_dir"
    description = "列出目录下的文件与子目录。"
    args_model = ListDirArgs

    def run(self, path: str = ".") -> str:
        p = Path(path)
        if not p.exists():
            return f"错误: 路径不存在: {path}"
        if not p.is_dir():
            return f"错误: 不是目录: {path}"
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        if not entries:
            return "(空目录)"
        lines = []
        for entry in entries:
            if entry.is_dir():
                lines.append(f"{entry.name}/")
            else:
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                lines.append(f"{entry.name} ({size} B)")
        return "\n".join(lines)
