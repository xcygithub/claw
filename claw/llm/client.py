"""基于 litellm 的统一 LLM 客户端, 支持多模型切换与函数调用。"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import litellm

litellm.drop_params = True


@dataclass
class ToolCall:
    """模型请求的一次工具调用。"""

    id: str
    name: str
    arguments: str  # 原始 JSON 字符串


@dataclass
class LLMResponse:
    """LLM 返回的助手消息(已规范化)。"""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)


class LLMClient:
    """封装 litellm.completion, 提供重试与结果规范化。"""

    def __init__(
        self,
        model: str,
        max_retries: int = 3,
        api_base: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.max_retries = max_retries
        self.api_base = api_base
        self.api_key = api_key

    def _extra_params(self) -> dict[str, Any]:
        """仅在显式配置时传入 api_base / api_key, 否则交给 litellm 读环境变量。"""
        params: dict[str, Any] = {}
        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """调用模型, 带指数退避重试。"""
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = litellm.completion(
                    model=self.model,
                    messages=messages,
                    tools=tools or None,
                    tool_choice="auto" if tools else None,
                    temperature=temperature,
                    **self._extra_params(),
                )
                return self._normalize(response)
            except Exception as exc:  # noqa: BLE001 - 统一重试网络/限流错误
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM 调用失败(已重试 {self.max_retries} 次): {last_error}")

    def complete_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        on_delta: Callable[[str], None] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """流式调用: 实时通过 on_delta 推送文本增量, 结束后返回完整响应。

        工具调用(tool_calls)在流式分片中是逐段拼接的, 这里收集全部分片后
        用 litellm.stream_chunk_builder 重建出标准响应再规范化。
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                stream = litellm.completion(
                    model=self.model,
                    messages=messages,
                    tools=tools or None,
                    tool_choice="auto" if tools else None,
                    temperature=temperature,
                    stream=True,
                    **self._extra_params(),
                )
                chunks = []
                for chunk in stream:
                    chunks.append(chunk)
                    if on_delta:
                        try:
                            delta = chunk.choices[0].delta
                            content = getattr(delta, "content", None)
                        except (AttributeError, IndexError):
                            content = None
                        if content:
                            on_delta(content)
                rebuilt = litellm.stream_chunk_builder(chunks, messages=messages)
                return self._normalize(rebuilt)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(
            f"LLM 流式调用失败(已重试 {self.max_retries} 次): {last_error}"
        )

    def summarize(self, messages: list[dict[str, Any]]) -> str:
        """无工具的纯文本补全, 用于上下文压缩生成摘要。"""
        response = litellm.completion(
            model=self.model,
            messages=messages,
            temperature=0.0,
            **self._extra_params(),
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _normalize(response: Any) -> LLMResponse:
        message = response.choices[0].message
        tool_calls: list[ToolCall] = []
        for call in getattr(message, "tool_calls", None) or []:
            tool_calls.append(
                ToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=call.function.arguments or "{}",
                )
            )

        # 转成可序列化的 dict, 便于追加进消息历史
        raw_message: dict[str, Any] = {"role": "assistant", "content": message.content}
        if tool_calls:
            raw_message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in tool_calls
            ]

        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            raw_message=raw_message,
            usage=usage,
        )
