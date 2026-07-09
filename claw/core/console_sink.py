"""终端事件接收器: 把 Agent 事件渲染到 rich 控制台。"""

from __future__ import annotations

from typing import Any

from claw import ui
from claw.core.events import EventSink


class ConsoleEventSink(EventSink):
    """包装现有终端 UI。启用流式: 边收边渲染回复正文与思考过程。"""

    streaming = True

    def __init__(self) -> None:
        self._reasoning_live: Any = None
        self._reasoning_text = ""
        self._assistant_live: Any = None
        self._assistant_text = ""

    # --- 思考过程(仅推理模型会触发) ---
    def on_reasoning_delta(self, delta: str) -> None:
        if self._reasoning_live is None:
            self._reasoning_live = ui.start_reasoning_stream()
            self._reasoning_text = ""
        self._reasoning_text += delta
        ui.update_reasoning_stream(self._reasoning_live, self._reasoning_text)

    def _end_reasoning(self) -> None:
        if self._reasoning_live is not None:
            ui.stop_reasoning_stream(self._reasoning_live, len(self._reasoning_text))
            self._reasoning_live = None
            self._reasoning_text = ""

    # --- 正文流式 ---
    def on_assistant_delta(self, delta: str) -> None:
        self._end_reasoning()
        if self._assistant_live is None:
            self._assistant_live = ui.start_assistant_stream()
            self._assistant_text = ""
        self._assistant_text += delta
        ui.update_assistant_stream(self._assistant_live, self._assistant_text)

    def on_assistant_end(self) -> None:
        self._end_reasoning()
        if self._assistant_live is not None:
            ui.stop_assistant_stream(self._assistant_live)
            self._assistant_live = None
            self._assistant_text = ""

    def on_assistant_text(self, text: str) -> None:
        # 兜底: 若某处仍以非流式方式给出完整文本, 直接一次性渲染。
        ui.assistant_message(text)

    def on_tool_call(self, name: str, preview: str) -> None:
        self._end_reasoning()
        ui.tool_call(preview)

    def on_tool_result(self, name: str, result: str) -> None:
        ui.tool_result(result, label=name)

    def on_info(self, message: str) -> None:
        self._end_reasoning()
        ui.info(message)

    def on_warning(self, message: str) -> None:
        self._end_reasoning()
        ui.warning(message)

    def on_error(self, message: str) -> None:
        self._end_reasoning()
        ui.error(message)

    def on_todos(self, rendered: str) -> None:
        ui.todo_list(rendered)

    def request_approval(self, name: str, preview: str, dangerous: bool) -> str:
        return ui.confirm(preview, dangerous=dangerous)
