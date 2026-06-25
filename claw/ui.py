"""基于 rich 的终端渲染。"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

console = Console()


def banner(model: str) -> None:
    console.print(
        Panel.fit(
            Text.from_markup(
                "[bold]Claw[/bold] 编程助手  "
                f"[dim]模型: {model}[/dim]\n"
                "[dim]输入任务开始; /help 查看命令; /exit 退出[/dim]"
            ),
            border_style="cyan",
        )
    )


def assistant_message(content: str) -> None:
    if not content.strip():
        return
    console.print(Markdown(content))


def tool_call(preview: str) -> None:
    console.print(f"[cyan]›[/cyan] [bold]{preview}[/bold]")


def tool_result(content: str, max_lines: int = 15) -> None:
    lines = content.splitlines()
    shown = lines[:max_lines]
    text = "\n".join(shown)
    if len(lines) > max_lines:
        text += f"\n[dim]... (省略 {len(lines) - max_lines} 行)[/dim]"
    console.print(Panel(text, border_style="dim", expand=False))


def error(message: str) -> None:
    console.print(f"[bold red]错误:[/bold red] {message}")


def info(message: str) -> None:
    console.print(f"[dim]{message}[/dim]")


def warning(message: str) -> None:
    console.print(f"[bold yellow]{message}[/bold yellow]")


def confirm(prompt: str, dangerous: bool = False) -> str:
    """返回用户输入(已 strip 小写)。"""
    style = "bold red" if dangerous else "bold yellow"
    tag = " [危险操作]" if dangerous else ""
    console.print(f"[{style}]需要确认{tag}:[/{style}] {prompt}")
    answer = console.input("  允许? [y=是 / n=否 / a=本次会话全部允许]: ")
    return answer.strip().lower()
