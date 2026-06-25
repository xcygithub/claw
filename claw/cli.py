"""命令行入口: 交互式 REPL 与单次模式。"""

from __future__ import annotations

import sys

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from claw import ui
from claw.agent import Agent
from claw.config import load_settings
from claw.llm.client import LLMClient
from claw.memory import load_project_memory
from claw.messages import Conversation
from claw.prompts import build_system_prompt
from claw.safety import SafetyManager
from claw.tools import build_default_registry

HELP_TEXT = """可用命令:
  /help            显示帮助
  /model <名称>    切换模型 (litellm 标识)
  /tools           列出已注册的工具
  /clear           清空对话历史
  /compact         手动压缩对话历史
  /exit, /quit     退出
"""


class ClawApp:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.client = LLMClient(
            model=self.settings.model,
            api_base=self.settings.api_base,
            api_key=self.settings.api_key,
        )
        self.safety = SafetyManager(auto_approve=self.settings.auto_approve)
        self.registry = build_default_registry(memory_path=self.settings.memory_file)
        memory = load_project_memory(self.settings.memory_file)
        if memory:
            ui.info(f"已加载项目记忆: {self.settings.memory_file}")
        self.conversation = Conversation(build_system_prompt(memory))
        self.agent = Agent(
            client=self.client,
            registry=self.registry,
            conversation=self.conversation,
            safety=self.safety,
            settings=self.settings,
        )

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
                ui.info(f"当前模型: {self.settings.model}")
            else:
                self.settings.model = arg
                self.client.model = arg
                ui.info(f"已切换模型: {arg}")
        elif cmd == "/tools":
            for tool in self.registry.all():
                ui.console.print(f"  [cyan]{tool.name}[/cyan] - {tool.description}")
        elif cmd == "/clear":
            self.conversation.clear()
            ui.info("已清空对话历史。")
        elif cmd == "/compact":
            self.agent.compact_now()
            ui.info("已压缩对话历史。")
        else:
            ui.error(f"未知命令: {cmd} (用 /help 查看)")
        return False

    def run_repl(self) -> None:
        ui.banner(self.settings.model)
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
                self.agent.run_turn(line)
            except KeyboardInterrupt:
                ui.warning("\n已中断当前任务。")
            except Exception as exc:  # noqa: BLE001
                ui.error(str(exc))

    def run_once(self, task: str) -> None:
        try:
            self.agent.run_turn(task)
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
