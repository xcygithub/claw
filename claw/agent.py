"""Agent 核心: 工具调用循环(界面无关, 通过 EventSink 输出)。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from claw.config import Settings
from claw.core.events import EventSink
from claw.llm.client import LLMClient, LLMResponse, ToolCall
from claw.memory import compact_history, estimate_tokens
from claw.memory_extract import apply_candidates, extract_candidates
from claw.memory_store import MemoryStore
from claw.messages import Conversation
from claw.safety import SafetyManager
from claw.tools.base import Tool, ToolRegistry


@dataclass
class _PreparedCall:
    """一次工具调用经解析/确认后的待执行状态。"""

    call: ToolCall
    tool: Tool | None
    args: dict[str, Any]
    rejected: str | None  # 非 None 表示已拒绝/出错, 直接作为结果


class Agent:
    """驱动一次用户任务直到模型不再请求工具。"""

    def __init__(
        self,
        client: LLMClient,
        registry: ToolRegistry,
        conversation: Conversation,
        safety: SafetyManager,
        settings: Settings,
        sink: EventSink,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self.client = client
        self.registry = registry
        self.conversation = conversation
        self.safety = safety
        self.settings = settings
        self.sink = sink
        self.memory_store = memory_store

    def run_turn(self, user_input: str) -> None:
        """处理一轮用户输入。"""
        self.conversation.add_user(user_input)

        for _ in range(self.settings.max_iterations):
            if self.sink.is_cancelled():
                self.sink.on_warning("已停止当前任务。")
                return
            self._maybe_compact()
            response = self._get_response()
            self.conversation.add_assistant(response.raw_message)

            if not response.tool_calls:
                if not self.sink.streaming:
                    self.sink.on_assistant_text(response.content or "")
                return

            if (
                response.content
                and response.content.strip()
                and not self.sink.streaming
            ):
                self.sink.on_assistant_text(response.content)

            results = self._execute_tools(response.tool_calls)
            for call, result in results:
                self.conversation.add_tool_result(call.id, call.name, result)

        self.sink.on_warning(
            f"已达到最大迭代次数 ({self.settings.max_iterations}), 本轮停止。"
        )

    def _get_response(self) -> LLMResponse:
        """根据 sink 是否需要流式, 选择合适的 LLM 调用方式。"""
        tools = self.registry.schemas()
        if self.sink.streaming:
            response = self.client.complete_stream(
                messages=self.conversation.messages,
                tools=tools,
                on_delta=self.sink.on_assistant_delta,
                on_reasoning_delta=self.sink.on_reasoning_delta,
            )
            self.sink.on_assistant_end()
            return response
        return self.client.complete(messages=self.conversation.messages, tools=tools)

    def _execute_tools(self, calls: list[ToolCall]) -> list[tuple[ToolCall, str]]:
        """先串行做解析与用户确认, 再并行执行已批准的工具, 最后按原序返回结果。"""
        prepared = [self._prepare_call(call) for call in calls]

        runnable = [
            (idx, p)
            for idx, p in enumerate(prepared)
            if p.rejected is None and p.tool is not None
        ]
        results: dict[int, str] = {
            idx: p.rejected for idx, p in enumerate(prepared) if p.rejected is not None
        }

        if len(runnable) <= 1:
            for idx, p in runnable:
                results[idx] = self._run_one(p.tool, p.args)
        else:
            workers = min(len(runnable), self.settings.max_parallel_tools)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_idx = {
                    executor.submit(self._run_one, p.tool, p.args): idx
                    for idx, p in runnable
                }
                for future in as_completed(future_to_idx):
                    results[future_to_idx[future]] = future.result()

        output: list[tuple[ToolCall, str]] = []
        for idx, p in enumerate(prepared):
            result = self._truncate(results.get(idx, ""))
            self.sink.on_tool_result(p.call.name, result)
            output.append((p.call, result))
        return output

    def _prepare_call(self, call: ToolCall) -> _PreparedCall:
        """解析参数并(在需要时)向用户确认。"""
        tool = self.registry.get(call.name)
        if tool is None:
            return _PreparedCall(call, None, {}, f"错误: 未知工具 {call.name}")

        try:
            args = json.loads(call.arguments or "{}")
        except json.JSONDecodeError as exc:
            return _PreparedCall(call, None, {}, f"错误: 工具参数 JSON 解析失败: {exc}")

        self.sink.on_tool_call(call.name, tool.preview(**args))

        command = args.get("command") if call.name == "run_command" else None
        if self.safety.needs_confirmation(tool.name, tool.mutating, command):
            dangerous = bool(command and self.safety.is_dangerous_command(command))
            answer = self.sink.request_approval(
                call.name, tool.preview(**args), dangerous
            )
            answer = (answer or "").strip().lower()
            if answer == "a" and not dangerous:
                self.safety.remember_approve_all()
            elif answer not in ("y", "yes", "a"):
                return _PreparedCall(call, tool, args, "用户拒绝了该操作。")

        return _PreparedCall(call, tool, args, None)

    @staticmethod
    def _run_one(tool: Tool, args: dict[str, Any]) -> str:
        try:
            return tool.run(**args)
        except Exception as exc:  # noqa: BLE001
            return f"错误: 工具执行异常: {exc}"

    def _truncate(self, text: str) -> str:
        limit = self.settings.max_tool_output_chars
        if len(text) <= limit:
            return text
        return text[:limit] + f"\n... (输出过长, 已截断, 共 {len(text)} 字符)"

    def _maybe_compact(self) -> None:
        threshold = int(self.settings.context_window() * self.settings.compact_threshold)
        if estimate_tokens(self.conversation.messages) < threshold:
            return
        self.sink.on_info("上下文接近上限, 正在压缩历史...")
        self.extract_memory_now()
        compacted = compact_history(self.client, self.conversation.messages)
        self.conversation.set_messages(compacted)
        self.sink.on_info("历史已压缩。")

    def compact_now(self) -> None:
        """手动触发压缩(供 /compact 命令使用)。"""
        self.extract_memory_now()
        compacted = compact_history(self.client, self.conversation.messages)
        self.conversation.set_messages(compacted)

    def extract_memory_now(self) -> int:
        """从当前对话里自动提取候选记忆并写入(source=auto)。返回新增条数。

        供压缩/清空历史前调用, 避免旧对话被丢弃后知识彻底丢失; 关闭
        ``auto_memory_extract`` 或没有绑定 memory_store 时直接跳过。
        """
        if not self.memory_store or not self.settings.auto_memory_extract:
            return 0
        try:
            candidates = extract_candidates(self.client, self.conversation.messages)
            added = apply_candidates(self.memory_store, candidates, scope="project")
        except Exception:  # noqa: BLE001 - 提取失败不应影响压缩/清空主流程
            return 0
        if added:
            self.sink.on_info(f"已自动提取 {added} 条记忆到项目记忆。")
        return added
