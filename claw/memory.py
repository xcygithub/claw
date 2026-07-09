"""上下文压缩(自动摘要)。结构化记忆的读写见 ``claw.memory_store``。"""

from __future__ import annotations

from typing import Any

from claw.llm.client import LLMClient

_COMPACT_INSTRUCTION = """请把下面这段编程会话历史压缩成简洁的中文摘要, 用于在后续对话中替代原始记录。
务必保留:
1. 用户的目标与关键需求
2. 已完成的工作与改动过的文件
3. 仍未完成的任务 / 待办
4. 关键结论、踩过的坑、重要的代码事实

不要编造内容, 只总结已发生的。输出纯文本摘要即可。"""


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """粗略估算消息总 token 数(约 4 字符/token, 中文偏保守)。"""
    chars = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            chars += len(content)
        for call in msg.get("tool_calls", []) or []:
            chars += len(str(call.get("function", {}).get("arguments", "")))
    return chars // 3


def render_transcript(messages: list[dict[str, Any]]) -> str:
    """把消息列表转成给摘要/提取模型看的纯文本记录。

    tool 角色消息必须紧跟其 assistant tool_calls, 单独提交易破坏配对,
    这里只把它们转成纯文本描述, 不再作为独立的 tool 消息提交。
    """
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "?")
        content = msg.get("content") or ""
        if msg.get("tool_calls"):
            names = ", ".join(
                c.get("function", {}).get("name", "?") for c in msg["tool_calls"]
            )
            content = (content + f" [调用工具: {names}]").strip()
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def compact_history(
    client: LLMClient,
    messages: list[dict[str, Any]],
    keep_recent: int = 6,
) -> list[dict[str, Any]]:
    """把较早的消息压缩成一条摘要, 保留最近 keep_recent 条原文。

    第 0 条(system)始终保留。返回新的消息列表。
    """
    if len(messages) <= keep_recent + 1:
        return messages

    system_msg = messages[0]
    recent = messages[-keep_recent:]
    to_compress = messages[1:-keep_recent]
    if not to_compress:
        return messages

    transcript = render_transcript(to_compress)
    summary = client.summarize(
        [
            {"role": "system", "content": _COMPACT_INSTRUCTION},
            {"role": "user", "content": transcript},
        ]
    )

    summary_msg = {
        "role": "user",
        "content": f"[之前对话的摘要]\n{summary}",
    }
    return [system_msg, summary_msg, *recent]
