"""自动记忆提取: 压缩/清空历史前, 让模型从对话里挑出值得长期记住的候选条目。

作为 `update_memory` 工具(模型主动调用)之外的安全网, 减少"模型忘了主动记录"
导致的知识丢失; 提取失败或解析失败时静默跳过, 不影响主流程。
"""

from __future__ import annotations

import json
import re
from typing import Any

from claw.llm.client import LLMClient
from claw.memory import render_transcript
from claw.memory_store import MemoryEntry, MemoryStore

_EXTRACT_INSTRUCTION = """你正在帮一个编程助手 Agent 整理长期记忆。
请阅读下面这段对话历史, 找出其中值得长期记住、对以后的会话仍然有用的信息, 例如:
- 项目的架构决策、技术栈选型、目录结构与命名约定
- 用户明确表达的偏好(编码风格、语言习惯、常用命令)
- 踩过的坑、易错点、重要结论

不要记录临时性、一次性的流水账(比如"这次改了哪一行"这种)。
如果没有值得记住的内容, 输出空数组 []。

只输出一个 JSON 数组, 不要输出任何其他文字, 每个元素形如:
{"content": "具体内容", "section": "小节标题(可选)", "tags": ["标签1", "标签2"], "importance": "low|normal|high"}"""

_VALID_IMPORTANCE = ("low", "normal", "high")
_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def extract_candidates(
    client: LLMClient, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """调用模型从对话中抽取候选记忆; 任何异常都返回空列表而不是抛出。"""
    transcript = render_transcript(messages).strip()
    if not transcript:
        return []
    try:
        raw = client.summarize(
            [
                {"role": "system", "content": _EXTRACT_INSTRUCTION},
                {"role": "user", "content": transcript},
            ]
        )
    except Exception:  # noqa: BLE001
        return []
    return _parse_candidates(raw)


def _parse_candidates(raw: str) -> list[dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return []
    match = _ARRAY_RE.search(raw)
    text = match.group(0) if match else raw
    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, list):
        return []

    candidates: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        importance = item.get("importance", "normal")
        if importance not in _VALID_IMPORTANCE:
            importance = "normal"
        tags_raw = item.get("tags") or []
        tags = [str(t).strip() for t in tags_raw if str(t).strip()] if isinstance(tags_raw, list) else []
        section = item.get("section")
        candidates.append(
            {
                "content": content,
                "section": str(section).strip() if section else None,
                "tags": tags,
                "importance": importance,
            }
        )
    return candidates


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _is_duplicate(content: str, existing: list[MemoryEntry], threshold: float = 0.6) -> bool:
    """用词集合的 Jaccard 相似度粗略判断是否与已有记忆重复, 避免自动提取刷屏。"""
    tokens = _tokenize(content)
    if not tokens:
        return False
    for entry in existing:
        other = _tokenize(entry.content)
        if not other:
            continue
        union = tokens | other
        if not union:
            continue
        if len(tokens & other) / len(union) >= threshold:
            return True
    return False


def apply_candidates(
    store: MemoryStore,
    candidates: list[dict[str, Any]],
    scope: str = "project",
) -> int:
    """把去重后的候选写入记忆库(source=auto), 返回实际新增的条数。"""
    existing = store.all(scope)
    added = 0
    for cand in candidates:
        if _is_duplicate(cand["content"], existing):
            continue
        entry = store.add(
            content=cand["content"],
            section=cand.get("section"),
            tags=cand.get("tags"),
            importance=cand.get("importance", "normal"),
            scope=scope,
            source="auto",
        )
        existing.append(entry)
        added += 1
    return added
