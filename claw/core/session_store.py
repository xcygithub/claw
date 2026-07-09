"""会话持久化: 把对话消息快照存到用户数据目录, 支持重启后 ``/resume`` 恢复。

按"项目目录"分桶存放(cwd 的绝对路径取 hash 作为桶名), 同一项目下的历史会话
互不干扰; 桌面端没有明确的项目目录概念, 由调用方传入一个固定 key。
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from claw.core import storage

_MAX_PREVIEW_CHARS = 60


def key_for_path(path: str | Path = ".") -> str:
    """把项目目录的绝对路径映射成稳定的短 key。"""
    abs_path = str(Path(path).resolve())
    return hashlib.sha1(abs_path.encode("utf-8")).hexdigest()[:12]


def _first_user_preview(messages: list[dict[str, Any]]) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            content = str(msg.get("content") or "").strip().replace("\n", " ")
            if len(content) > _MAX_PREVIEW_CHARS:
                content = content[:_MAX_PREVIEW_CHARS] + "..."
            return content
    return ""


class SessionStore:
    """保存/加载某个分桶(项目或桌面端)下的会话快照, 一份会话对应一个 JSON 文件。"""

    def __init__(self, key: str) -> None:
        self.dir = storage.sessions_dir() / key
        self.session_id = uuid.uuid4().hex[:12]

    def _path(self, session_id: str) -> Path:
        return self.dir / f"{session_id}.json"

    def save(self, messages: list[dict[str, Any]]) -> None:
        """把当前完整消息列表落盘(覆盖写); 只有 system 消息时跳过(没有实际内容)。"""
        if len(messages) <= 1:
            return
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "id": self.session_id,
                "updated_at": time.time(),
                "preview": _first_user_preview(messages),
                "messages": messages,
            }
            self._path(self.session_id).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001 - 持久化失败不应影响主流程
            pass

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.dir.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in self.dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            items.append(
                {
                    "id": data.get("id", path.stem),
                    "updated_at": data.get("updated_at", 0.0),
                    "preview": data.get("preview", ""),
                }
            )
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return items[:limit]

    def load(self, session_id: str) -> list[dict[str, Any]] | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
        messages = data.get("messages")
        if not isinstance(messages, list):
            return None
        self.session_id = session_id  # 恢复后继续写入同一份快照, 而不是另开一份
        return messages

    def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except Exception:  # noqa: BLE001
            return False
