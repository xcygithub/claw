"""搜索工具: grep(内容搜索) 与 glob(文件名匹配)。

优先使用本机 ripgrep(rg) 提速, 不可用时回退到纯 Python 实现。
"""

from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from claw.tools.base import Tool

_MAX_RESULTS = 200


class GrepArgs(BaseModel):
    pattern: str = Field(description="正则表达式")
    path: str = Field(default=".", description="搜索的根目录")
    glob: str | None = Field(default=None, description="限定文件名模式, 如 *.py")


class GrepTool(Tool):
    name = "grep"
    description = "在文件内容中按正则搜索, 返回匹配的文件:行号:内容。优先用 ripgrep。"
    args_model = GrepArgs

    def run(self, pattern: str, path: str = ".", glob: str | None = None) -> str:
        if shutil.which("rg"):
            return self._ripgrep(pattern, path, glob)
        return self._python_grep(pattern, path, glob)

    def _ripgrep(self, pattern: str, path: str, glob: str | None) -> str:
        cmd = ["rg", "--line-number", "--no-heading", "--color", "never", pattern, path]
        if glob:
            cmd[1:1] = ["--glob", glob]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception as exc:  # noqa: BLE001
            return f"错误: ripgrep 执行失败: {exc}"
        if result.returncode not in (0, 1):
            return f"错误: {result.stderr.strip()}"
        lines = result.stdout.splitlines()
        if not lines:
            return "(无匹配)"
        truncated = lines[:_MAX_RESULTS]
        out = "\n".join(truncated)
        if len(lines) > _MAX_RESULTS:
            out += f"\n... (共 {len(lines)} 条, 仅显示前 {_MAX_RESULTS} 条)"
        return out

    def _python_grep(self, pattern: str, path: str, glob: str | None) -> str:
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return f"错误: 无效正则: {exc}"
        root = Path(path)
        results: list[str] = []
        for file in root.rglob("*"):
            if not file.is_file():
                continue
            if glob and not fnmatch.fnmatch(file.name, glob):
                continue
            if any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in file.parts):
                continue
            try:
                for lineno, line in enumerate(
                    file.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    if regex.search(line):
                        results.append(f"{file}:{lineno}:{line}")
                        if len(results) >= _MAX_RESULTS:
                            results.append(f"... (达到 {_MAX_RESULTS} 条上限)")
                            return "\n".join(results)
            except Exception:  # noqa: BLE001 - 跳过二进制/不可读文件
                continue
        return "\n".join(results) if results else "(无匹配)"


class GlobArgs(BaseModel):
    pattern: str = Field(description="glob 模式, 如 **/*.py 或 src/*.ts")
    path: str = Field(default=".", description="搜索的根目录")


class GlobTool(Tool):
    name = "glob"
    description = "按 glob 模式查找文件路径, 如 **/*.py。"
    args_model = GlobArgs

    def run(self, pattern: str, path: str = ".") -> str:
        root = Path(path)
        matches = [
            str(p)
            for p in root.glob(pattern)
            if not any(
                part in {".git", "__pycache__", "node_modules", ".venv"}
                for part in p.parts
            )
        ]
        if not matches:
            return "(无匹配文件)"
        matches.sort()
        truncated = matches[:_MAX_RESULTS]
        out = "\n".join(truncated)
        if len(matches) > _MAX_RESULTS:
            out += f"\n... (共 {len(matches)} 个, 仅显示前 {_MAX_RESULTS} 个)"
        return out
