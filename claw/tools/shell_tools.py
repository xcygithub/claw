"""Shell 命令执行工具。"""

from __future__ import annotations

import subprocess

from pydantic import BaseModel, Field

from claw.tools.base import Tool


class RunCommandArgs(BaseModel):
    command: str = Field(description="要执行的 shell 命令")
    cwd: str | None = Field(default=None, description="工作目录, 留空使用当前目录")
    timeout: int = Field(default=120, description="超时秒数")


class RunCommandTool(Tool):
    name = "run_command"
    description = (
        "在 shell 中执行命令并返回 stdout/stderr 与退出码。"
        "用于运行测试、构建、git 等。会受安全确认机制保护。"
    )
    args_model = RunCommandArgs
    mutating = True

    def run(self, command: str, cwd: str | None = None, timeout: int = 120) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"错误: 命令超时(>{timeout}s): {command}"
        except Exception as exc:  # noqa: BLE001
            return f"错误: 命令执行失败: {exc}"

        parts = [f"退出码: {result.returncode}"]
        if result.stdout.strip():
            parts.append(f"--- stdout ---\n{result.stdout.rstrip()}")
        if result.stderr.strip():
            parts.append(f"--- stderr ---\n{result.stderr.rstrip()}")
        if len(parts) == 1:
            parts.append("(无输出)")
        return "\n".join(parts)

    def preview(self, command: str = "", cwd: str | None = None, timeout: int = 120) -> str:
        loc = f" @ {cwd}" if cwd else ""
        return f"执行命令{loc}: {command}"
