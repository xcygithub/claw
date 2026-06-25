"""会话引擎门面: 装配核心组件并对外提供统一操作, 供 CLI 与 GUI 共用。"""

from __future__ import annotations

from typing import Any

from claw.agent import Agent
from claw.config import Settings, load_settings
from claw.core.events import EventSink
from claw.llm.client import LLMClient
from claw.memory import load_project_memory
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
    ) -> None:
        self.sink = sink
        self.settings = settings or load_settings()
        if memory_file:
            self.settings.memory_file = memory_file

        self.client = LLMClient(
            model=self.settings.model,
            api_base=self.settings.api_base,
            api_key=self.settings.api_key,
        )
        self.safety = SafetyManager(auto_approve=self.settings.auto_approve)
        self.todo_store = TodoStore()
        self.registry = build_default_registry(
            memory_path=self.settings.memory_file,
            todo_store=self.todo_store,
        )
        memory = load_project_memory(self.settings.memory_file)
        self.has_memory = bool(memory)
        self.conversation = Conversation(build_system_prompt(memory))
        self.agent = Agent(
            client=self.client,
            registry=self.registry,
            conversation=self.conversation,
            safety=self.safety,
            settings=self.settings,
            sink=self.sink,
        )

    # --- 会话操作 ---
    def send(self, user_input: str) -> None:
        self.agent.run_turn(user_input)

    def clear(self) -> None:
        self.conversation.clear()

    def compact(self) -> None:
        self.agent.compact_now()

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
