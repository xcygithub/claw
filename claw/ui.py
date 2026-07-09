"""基于 rich 的终端渲染。"""

from __future__ import annotations

from rich.console import Console
from rich.live import Live
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


def start_assistant_stream() -> Live:
    """开始一段流式助手回复: 用 rich.Live 边收边渲染 Markdown。"""
    live = Live(Markdown(""), console=console, refresh_per_second=12)
    live.start()
    return live


def update_assistant_stream(live: Live, text: str) -> None:
    if text.strip():
        live.update(Markdown(text))


def stop_assistant_stream(live: Live) -> None:
    live.stop()


def start_reasoning_stream() -> Live:
    """开始展示思考过程: 结束后不留痕(transient), 只保留一行完成提示。"""
    live = Live(
        Text("", style="dim italic"),
        console=console,
        refresh_per_second=12,
        transient=True,
    )
    live.start()
    return live


def update_reasoning_stream(live: Live, text: str) -> None:
    tail = text[-1200:]  # 思考内容可能很长, 终端只展示尾部, 避免刷屏
    live.update(Text(tail, style="dim italic"))


def stop_reasoning_stream(live: Live, char_count: int) -> None:
    live.stop()
    if char_count:
        console.print(f"[dim]已完成思考 ({char_count} 字)[/dim]")


def tool_call(preview: str) -> None:
    console.print(f"[cyan]›[/cyan] [bold]{preview}[/bold]")


def tool_result(content: str, max_lines: int = 15, label: str | None = None) -> None:
    lines = content.splitlines()
    shown = lines[:max_lines]
    text = "\n".join(shown)
    if len(lines) > max_lines:
        text += f"\n[dim]... (省略 {len(lines) - max_lines} 行)[/dim]"
    title = f"[dim]{label}[/dim]" if label else None
    console.print(Panel(text, border_style="dim", expand=False, title=title, title_align="left"))


def todo_list(rendered: str) -> None:
    console.print(Panel(rendered, border_style="magenta", title="任务清单", title_align="left", expand=False))


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
