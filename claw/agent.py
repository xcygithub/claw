"""Agent 核心: 工具调用循环。"""

from __future__ import annotations

import json

from claw import ui
from claw.config import Settings
from claw.llm.client import LLMClient, ToolCall
from claw.memory import compact_history, estimate_tokens
from claw.messages import Conversation
from claw.safety import SafetyManager
from claw.tools.base import ToolRegistry


class Agent:
    """驱动一次用户任务直到模型不再请求工具。"""

    def __init__(
        self,
        client: LLMClient,
        registry: ToolRegistry,
        conversation: Conversation,
        safety: SafetyManager,
        settings: Settings,
    ) -> None:
        self.client = client
        self.registry = registry
        self.conversation = conversation
        self.safety = safety
        self.settings = settings

    def run_turn(self, user_input: str) -> None:
        """处理一轮用户输入。"""
        self.conversation.add_user(user_input)

        for _ in range(self.settings.max_iterations):
            self._maybe_compact()
            response = self.client.complete(
                messages=self.conversation.messages,
                tools=self.registry.schemas(),
            )
            self.conversation.add_assistant(response.raw_message)

            if not response.tool_calls:
                ui.assistant_message(response.content or "")
                return

            if response.content and response.content.strip():
                ui.assistant_message(response.content)

            for call in response.tool_calls:
                result = self._execute_tool(call)
                self.conversation.add_tool_result(call.id, call.name, result)

        ui.warning(f"已达到最大迭代次数 ({self.settings.max_iterations}), 本轮停止。")

    def _execute_tool(self, call: ToolCall) -> str:
        tool = self.registry.get(call.name)
        if tool is None:
            return f"错误: 未知工具 {call.name}"

        try:
            args = json.loads(call.arguments or "{}")
        except json.JSONDecodeError as exc:
            return f"错误: 工具参数 JSON 解析失败: {exc}"

        preview = tool.preview(**args)
        ui.tool_call(preview)

        command = args.get("command") if call.name == "run_command" else None
        if self.safety.needs_confirmation(tool.name, tool.mutating, command):
            dangerous = bool(command and self.safety.is_dangerous_command(command))
            answer = ui.confirm(preview, dangerous=dangerous)
            if answer == "a" and not dangerous:
                self.safety.remember_approve_all()
            elif answer not in ("y", "yes", "a"):
                return "用户拒绝了该操作。"

        try:
            result = tool.run(**args)
        except Exception as exc:  # noqa: BLE001
            result = f"错误: 工具执行异常: {exc}"

        result = self._truncate(result)
        ui.tool_result(result)
        return result

    def _truncate(self, text: str) -> str:
        limit = self.settings.max_tool_output_chars
        if len(text) <= limit:
            return text
        return text[:limit] + f"\n... (输出过长, 已截断, 共 {len(text)} 字符)"

    def _maybe_compact(self) -> None:
        threshold = int(self.settings.context_window() * self.settings.compact_threshold)
        if estimate_tokens(self.conversation.messages) < threshold:
            return
        ui.info("上下文接近上限, 正在压缩历史...")
        compacted = compact_history(self.client, self.conversation.messages)
        self.conversation.set_messages(compacted)
        ui.info("历史已压缩。")

    def compact_now(self) -> None:
        """手动触发压缩(供 /compact 命令使用)。"""
        compacted = compact_history(self.client, self.conversation.messages)
        self.conversation.set_messages(compacted)
