"""终端事件接收器: 把 Agent 事件渲染到 rich 控制台。"""

from __future__ import annotations

from claw import ui
from claw.core.events import EventSink


class ConsoleEventSink(EventSink):
    """包装现有终端 UI。保持非流式以使用 Markdown 渲染。"""

    streaming = False

    def on_assistant_text(self, text: str) -> None:
        ui.assistant_message(text)

    def on_tool_call(self, name: str, preview: str) -> None:
        ui.tool_call(preview)

    def on_tool_result(self, name: str, result: str) -> None:
        ui.tool_result(result, label=name)

    def on_info(self, message: str) -> None:
        ui.info(message)

    def on_warning(self, message: str) -> None:
        ui.warning(message)

    def on_error(self, message: str) -> None:
        ui.error(message)

    def on_todos(self, rendered: str) -> None:
        ui.todo_list(rendered)

    def request_approval(self, name: str, preview: str, dangerous: bool) -> str:
        return ui.confirm(preview, dangerous=dangerous)
