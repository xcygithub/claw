"""命令行入口: 交互式 REPL 与单次模式。"""

from __future__ import annotations

import sys

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from claw import ui
from claw.core.console_sink import ConsoleEventSink
from claw.core.engine import ClawEngine

HELP_TEXT = """可用命令:
  /help            显示帮助
  /model <名称>    切换模型 (litellm 标识)
  /tools           列出已注册的工具
  /todos           显示当前任务清单
  /clear           清空对话历史
  /compact         手动压缩对话历史
  /exit, /quit     退出
"""


class ClawApp:
    def __init__(self) -> None:
        self.sink = ConsoleEventSink()
        self.engine = ClawEngine(sink=self.sink)
        if self.engine.has_memory:
            ui.info(f"已加载项目记忆: {self.engine.settings.memory_file}")

    def handle_command(self, line: str) -> bool:
        """处理斜杠命令; 返回 True 表示应退出。"""
        parts = line.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            return True
        if cmd == "/help":
            ui.console.print(HELP_TEXT)
        elif cmd == "/model":
            if not arg:
                ui.info(f"当前模型: {self.engine.settings.model}")
            else:
                self.engine.switch_model(arg)
                ui.info(f"已切换模型: {arg}")
        elif cmd == "/tools":
            for name, desc in self.engine.list_tools():
                ui.console.print(f"  [cyan]{name}[/cyan] - {desc}")
        elif cmd == "/todos":
            ui.todo_list(self.engine.render_todos())
        elif cmd == "/clear":
            self.engine.clear()
            ui.info("已清空对话历史。")
        elif cmd == "/compact":
            self.engine.compact()
            ui.info("已压缩对话历史。")
        else:
            ui.error(f"未知命令: {cmd} (用 /help 查看)")
        return False

    def run_repl(self) -> None:
        ui.banner(self.engine.settings.model)
        session: PromptSession = PromptSession(history=InMemoryHistory())
        while True:
            try:
                line = session.prompt("\nclaw › ")
            except (EOFError, KeyboardInterrupt):
                ui.info("\n再见。")
                break

            line = line.strip()
            if not line:
                continue
            if line.startswith("/"):
                if self.handle_command(line):
                    ui.info("再见。")
                    break
                continue

            try:
                self.engine.send(line)
            except KeyboardInterrupt:
                ui.warning("\n已中断当前任务。")
            except Exception as exc:  # noqa: BLE001
                ui.error(str(exc))

    def run_once(self, task: str) -> None:
        try:
            self.engine.send(task)
        except Exception as exc:  # noqa: BLE001
            ui.error(str(exc))
            sys.exit(1)


def main() -> None:
    load_dotenv()
    args = sys.argv[1:]
    app = ClawApp()
    if args:
        app.run_once(" ".join(args))
    else:
        app.run_repl()


if __name__ == "__main__":
    main()
