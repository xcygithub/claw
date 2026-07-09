"""命令行入口: 交互式 REPL 与单次模式。"""

from __future__ import annotations

import sys
from datetime import datetime

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from claw import ui
from claw.core.console_sink import ConsoleEventSink
from claw.core.engine import ClawEngine

HELP_TEXT = """可用命令:
  /help                    显示帮助
  /model <名称>            切换模型 (litellm 标识)
  /tools                   列出已注册的工具
  /todos                   显示当前任务清单
  /clear                   清空对话历史
  /compact                 手动压缩对话历史
  /memory                  列出全部记忆条目(项目 CLAW.md + 全局 GLOBAL.md)
  /memory search <关键词>  按关键词检索记忆
  /memory forget <id>      删除指定 id 的记忆条目
  /resume                  列出可恢复的历史会话
  /resume <序号>           恢复对应的历史会话, 继续上次对话
  /exit, /quit             退出

启动参数:
  claw --continue / -c     启动时自动恢复最近一次会话
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
        elif cmd == "/memory":
            self._handle_memory(arg)
        elif cmd == "/resume":
            self._handle_resume(arg)
        else:
            ui.error(f"未知命令: {cmd} (用 /help 查看)")
        return False

    def _handle_memory(self, arg: str) -> None:
        parts = arg.split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if not sub:
            self._print_memory_entries(self.engine.list_memory())
        elif sub == "search":
            if not rest:
                ui.error("用法: /memory search <关键词>")
                return
            self._print_memory_entries(self.engine.search_memory(rest))
        elif sub == "forget":
            if not rest:
                ui.error("用法: /memory forget <id>")
                return
            if self.engine.delete_memory_entry(rest):
                ui.info(f"已删除记忆条目 {rest}")
            else:
                ui.error(f"未找到记忆条目 {rest}")
        else:
            ui.error("用法: /memory | /memory search <关键词> | /memory forget <id>")

    @staticmethod
    def _print_memory_entries(entries: list[dict]) -> None:
        if not entries:
            ui.info("(暂无记忆)")
            return
        for e in entries:
            scope_label = "全局" if e["scope"] == "global" else "项目"
            tag_str = f" #{' #'.join(e['tags'])}" if e["tags"] else ""
            ui.console.print(
                f"  [cyan]{e['id']}[/cyan] "
                f"[{scope_label}/{e['section']}] "
                f"({e['importance']}/{e['source']}){tag_str} {e['content']}"
            )

    def _handle_resume(self, arg: str) -> None:
        sessions = self.engine.list_sessions(limit=10)
        if not sessions:
            ui.info("没有可恢复的历史会话。")
            return

        if not arg:
            for i, s in enumerate(sessions, 1):
                ts = (
                    datetime.fromtimestamp(s["updated_at"]).strftime("%Y-%m-%d %H:%M")
                    if s.get("updated_at")
                    else "?"
                )
                ui.console.print(f"  [{i}] {ts}  {s['preview'] or '(无预览)'}")
            ui.info("用 /resume <序号> 恢复对应会话。")
            return

        try:
            idx = int(arg.strip())
        except ValueError:
            ui.error("用法: /resume [序号]")
            return
        if not (1 <= idx <= len(sessions)):
            ui.error(f"序号超出范围(1-{len(sessions)})")
            return

        if self.engine.resume(sessions[idx - 1]["id"]):
            ui.info("已恢复该会话, 可继续对话。")
        else:
            ui.error("恢复会话失败。")

    def try_resume_latest(self) -> bool:
        """启动参数 --continue/-c 用: 自动恢复最近一次会话。返回是否成功。"""
        sessions = self.engine.list_sessions(limit=1)
        if not sessions:
            ui.info("没有可恢复的历史会话, 将开始新会话。")
            return False
        if self.engine.resume(sessions[0]["id"]):
            ui.info(f"已恢复上次会话: {sessions[0]['preview'] or '(无预览)'}")
            return True
        ui.error("恢复会话失败, 将开始新会话。")
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
    continue_flag = False
    for flag in ("--continue", "-c"):
        while flag in args:
            args.remove(flag)
            continue_flag = True

    app = ClawApp()
    if continue_flag:
        app.try_resume_latest()
    if args:
        app.run_once(" ".join(args))
    else:
        app.run_repl()


if __name__ == "__main__":
    main()
