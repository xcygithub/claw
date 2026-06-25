"""事件接口: 解耦 Agent 核心与具体界面(终端 / GUI)。

Agent 不再直接调用终端渲染, 而是把结构化事件发给一个 EventSink。
不同界面实现不同的 Sink:
- 终端: ConsoleEventSink(包装 rich UI)
- 桌面 GUI: WebEventSink(把事件推给前端, 见 claw/app.py)
"""

from __future__ import annotations


class EventSink:
    """Agent 运行时的事件接收器。

    所有方法都提供默认空实现, 子类只需覆盖关心的事件。
    ``streaming`` 为 True 时, Agent 会用流式接口并通过
    ``on_assistant_delta`` 持续推送增量文本; 否则用 ``on_assistant_text``
    一次性给出完整回复。
    """

    streaming: bool = False

    def on_assistant_text(self, text: str) -> None:
        """非流式: 一条完整的助手文本回复。"""

    def on_assistant_delta(self, delta: str) -> None:
        """流式: 一段增量文本。"""

    def on_assistant_end(self) -> None:
        """流式: 当前助手消息结束。"""

    def on_tool_call(self, name: str, preview: str) -> None:
        """即将执行某个工具。"""

    def on_tool_result(self, name: str, result: str) -> None:
        """某个工具执行完毕。"""

    def on_info(self, message: str) -> None:
        """提示性信息。"""

    def on_warning(self, message: str) -> None:
        """警告。"""

    def on_error(self, message: str) -> None:
        """错误。"""

    def on_todos(self, rendered: str) -> None:
        """任务清单更新(已渲染文本)。"""

    def request_approval(self, name: str, preview: str, dangerous: bool) -> str:
        """请求用户确认一次有副作用的操作。

        返回值约定(已 strip 小写): ``y``/``yes`` 允许, ``a`` 本次会话全部允许,
        其他一律视为拒绝。默认实现保守地拒绝。
        """
        return "n"

    def is_cancelled(self) -> bool:
        """用户是否请求中断当前任务(协作式取消)。"""
        return False
