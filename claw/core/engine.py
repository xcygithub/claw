"""会话引擎门面: 装配核心组件并对外提供统一操作, 供 CLI 与 GUI 共用。"""

from __future__ import annotations

from typing import Any

from claw.agent import Agent
from claw.config import Settings, load_settings
from claw.core import storage
from claw.core.events import EventSink
from claw.core.session_store import SessionStore, key_for_path
from claw.llm.client import LLMClient
from claw.memory_store import MemoryEntry, MemoryStore
from claw.messages import Conversation
from claw.prompts import build_system_prompt
from claw.safety import SafetyManager
from claw.todos import TodoStore
from claw.tools import build_default_registry


class ClawEngine:
    """封装一次完整会话所需的全部状态与操作。"""

    def __init__(
        self,
        sink: EventSink,
        settings: Settings | None = None,
        memory_file: str | None = None,
        global_memory_file: str | None = None,
        session_key: str | None = None,
    ) -> None:
        self.sink = sink
        self.settings = settings or load_settings()
        if memory_file:
            self.settings.memory_file = memory_file
        if global_memory_file:
            self.settings.memory_global_file = global_memory_file
        if not self.settings.memory_global_file:
            self.settings.memory_global_file = str(storage.global_memory_path())

        self.client = LLMClient(
            model=self.settings.model,
            api_base=self.settings.api_base,
            api_key=self.settings.api_key,
        )
        self.safety = SafetyManager(auto_approve=self.settings.auto_approve)
        self.todo_store = TodoStore()
        self.memory_store = MemoryStore(
            project_path=self.settings.memory_file,
            global_path=self.settings.memory_global_file,
        )
        self.session_store = SessionStore(session_key or key_for_path("."))
        self.registry = build_default_registry(
            memory_store=self.memory_store,
            todo_store=self.todo_store,
        )
        digest = self.memory_store.render_digest(self.settings.memory_digest_chars)
        self.has_memory = bool(digest)
        self.conversation = Conversation(build_system_prompt(digest))
        self.agent = Agent(
            client=self.client,
            registry=self.registry,
            conversation=self.conversation,
            safety=self.safety,
            settings=self.settings,
            sink=self.sink,
            memory_store=self.memory_store,
        )

    # --- 会话操作 ---
    def send(self, user_input: str) -> None:
        self._refresh_system_prompt()
        self.agent.run_turn(user_input)
        if self.settings.session_persist:
            self.session_store.save(self.conversation.messages)

    def clear(self) -> None:
        if len(self.conversation.messages) > 1:
            self.agent.extract_memory_now()
        self.conversation.clear()
        self._refresh_system_prompt()

    def compact(self) -> None:
        self.agent.compact_now()

    # --- 会话持久化(重启后恢复) ---
    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.session_store.list_recent(limit)

    def resume(self, session_id: str) -> bool:
        messages = self.session_store.load(session_id)
        if messages is None:
            return False
        self.conversation.set_messages(messages)
        self._refresh_system_prompt()
        return True

    def _refresh_system_prompt(self) -> None:
        """用最新的记忆摘要重建 system prompt(记忆可能在会话中被读写工具/UI 改动)。"""
        digest = self.memory_store.render_digest(self.settings.memory_digest_chars)
        self.has_memory = bool(digest)
        self.conversation.update_system_prompt(build_system_prompt(digest))

    # --- 配置 ---
    def switch_model(self, name: str) -> None:
        self.settings.model = name
        self.client.model = name

    def get_config(self) -> dict[str, Any]:
        return {
            "model": self.settings.model,
            "api_base": self.settings.api_base or "",
            "auto_approve": self.settings.auto_approve,
            "has_api_key": bool(self.settings.api_key),
        }

    def set_config(
        self,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        auto_approve: bool | None = None,
    ) -> None:
        """更新运行时配置(不负责持久化, 由调用方决定是否落盘)。"""
        if model is not None:
            self.settings.model = model
            self.client.model = model
        if api_base is not None:
            self.settings.api_base = api_base or None
            self.client.api_base = api_base or None
        if api_key is not None:
            self.settings.api_key = api_key or None
            self.client.api_key = api_key or None
        if auto_approve is not None:
            self.settings.auto_approve = auto_approve
            self.safety.auto_approve = auto_approve

    # --- 信息 ---
    def list_tools(self) -> list[tuple[str, str]]:
        return [(t.name, t.description) for t in self.registry.all()]

    def render_todos(self) -> str:
        return self.todo_store.render()

    # --- 记忆管理(供 CLI /memory 命令与桌面端记忆面板共用) ---
    def list_memory(self, scope: str | None = None) -> list[dict[str, Any]]:
        return [_entry_to_dict(e) for e in self.memory_store.all(scope)]

    def search_memory(
        self, query: str, scope: str | None = None, top_k: int = 20
    ) -> list[dict[str, Any]]:
        return [
            _entry_to_dict(e) for e in self.memory_store.search(query, scope, top_k)
        ]

    def add_memory_entry(
        self,
        content: str,
        section: str | None = None,
        tags: list[str] | None = None,
        importance: str = "normal",
        scope: str = "project",
    ) -> dict[str, Any]:
        entry = self.memory_store.add(
            content=content,
            section=section,
            tags=tags,
            importance=importance,
            scope=scope,
            source="manual",
        )
        self._refresh_system_prompt()
        return _entry_to_dict(entry)

    def update_memory_entry(
        self,
        entry_id: str,
        content: str | None = None,
        section: str | None = None,
        tags: list[str] | None = None,
        importance: str | None = None,
    ) -> bool:
        ok = self.memory_store.update(
            entry_id, content=content, section=section, tags=tags, importance=importance
        )
        if ok:
            self._refresh_system_prompt()
        return ok

    def delete_memory_entry(self, entry_id: str) -> bool:
        ok = self.memory_store.delete(entry_id)
        if ok:
            self._refresh_system_prompt()
        return ok


def _entry_to_dict(entry: MemoryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "content": entry.content,
        "section": entry.section,
        "tags": entry.tags,
        "importance": entry.importance,
        "source": entry.source,
        "scope": entry.scope,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }
