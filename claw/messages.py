"""会话历史管理。"""

from __future__ import annotations

from typing import Any


class Conversation:
    """维护消息列表, 第 0 条固定为 system 消息。"""

    def __init__(self, system_prompt: str) -> None:
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

    @property
    def messages(self) -> list[dict[str, Any]]:
        return self._messages

    def set_messages(self, messages: list[dict[str, Any]]) -> None:
        """整体替换(用于压缩后回写)。"""
        self._messages = messages

    def update_system_prompt(self, system_prompt: str) -> None:
        self._messages[0] = {"role": "system", "content": system_prompt}

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, raw_message: dict[str, Any]) -> None:
        self._messages.append(raw_message)

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        self._messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": name,
                "content": content,
            }
        )

    def clear(self) -> None:
        """清空除 system 外的所有消息。"""
        self._messages = self._messages[:1]
