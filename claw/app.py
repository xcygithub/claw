"""LegalClaw 桌面入口: pywebview 外壳 + JS 桥接。

运行: ``python -m claw.app`` 或安装后的 ``legalclaw`` 命令。
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

from claw import APP_NAME, __version__
from claw.config import load_settings
from claw.core import storage
from claw.core.engine import ClawEngine
from claw.core.events import EventSink


def _frontend_dir() -> Path:
    """定位前端静态资源(开发态在仓库; 打包后在临时解包目录)。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "frontend"
    return Path(__file__).resolve().parent.parent / "frontend"


class WebEventSink(EventSink):
    """把 Agent 事件推送到前端; 启用流式输出。"""

    streaming = True

    def __init__(self) -> None:
        self._window: Any = None
        self._cancel = threading.Event()
        self._approval_lock = threading.Lock()
        self._approval_event = threading.Event()
        self._approval_result = "n"
        self._approval_id = 0

    def bind_window(self, window: Any) -> None:
        self._window = window

    def _emit(self, event_type: str, **data: Any) -> None:
        if self._window is None:
            return
        payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
        try:
            self._window.evaluate_js(f"window.__clawEvent({payload})")
        except Exception:  # noqa: BLE001 - 窗口关闭等情况忽略
            pass

    # --- EventSink ---
    def on_assistant_delta(self, delta: str) -> None:
        self._emit("assistant_delta", text=delta)

    def on_assistant_end(self) -> None:
        self._emit("assistant_end")

    def on_assistant_text(self, text: str) -> None:
        self._emit("assistant_text", text=text)

    def on_tool_call(self, name: str, preview: str) -> None:
        self._emit("tool_call", name=name, preview=preview)

    def on_tool_result(self, name: str, result: str) -> None:
        self._emit("tool_result", name=name, result=result)

    def on_info(self, message: str) -> None:
        self._emit("info", message=message)

    def on_warning(self, message: str) -> None:
        self._emit("warning", message=message)

    def on_error(self, message: str) -> None:
        self._emit("error", message=message)

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def request_approval(self, name: str, preview: str, dangerous: bool) -> str:
        with self._approval_lock:
            self._approval_id += 1
            req_id = self._approval_id
            self._approval_result = "n"
            self._approval_event.clear()
        self._emit(
            "approval_request",
            id=req_id,
            name=name,
            preview=preview,
            dangerous=dangerous,
        )
        # 等待前端回应; 被取消时直接拒绝
        while not self._approval_event.wait(timeout=0.2):
            if self._cancel.is_set():
                return "n"
        return self._approval_result

    # --- 供 Api 调用 ---
    def resolve_approval(self, answer: str) -> None:
        self._approval_result = (answer or "n").strip().lower()
        self._approval_event.set()

    def reset_cancel(self) -> None:
        self._cancel.clear()

    def cancel(self) -> None:
        self._cancel.set()


def _build_gui_settings():
    """合并: 环境默认 + 存储配置 + 钥匙串密钥。"""
    settings = load_settings()
    config = storage.load_config()
    if config.get("model"):
        settings.model = config["model"]
    if "api_base" in config:
        settings.api_base = config["api_base"] or None
    if "auto_approve" in config:
        settings.auto_approve = bool(config["auto_approve"])
    key = storage.get_api_key()
    if key:
        settings.api_key = key
    return settings


class Api:
    """暴露给前端 JS 的接口(window.pywebview.api.*)。"""

    def __init__(self) -> None:
        self.sink = WebEventSink()
        self.engine = ClawEngine(
            sink=self.sink,
            settings=_build_gui_settings(),
            memory_file=str(storage.memory_path()),
        )
        self._busy = threading.Lock()

    def bind_window(self, window: Any) -> None:
        self.sink.bind_window(window)

    def app_info(self) -> dict[str, Any]:
        return {"name": APP_NAME, "version": __version__}

    def send_message(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        if not self._busy.acquire(blocking=False):
            self.sink.on_warning("正在处理上一条消息, 请稍候。")
            return
        self.sink.reset_cancel()

        def worker() -> None:
            try:
                self.engine.send(text)
            except Exception as exc:  # noqa: BLE001
                self.sink.on_error(str(exc))
            finally:
                self.sink._emit("done")
                self._busy.release()

        threading.Thread(target=worker, daemon=True).start()

    def stop(self) -> None:
        self.sink.cancel()

    def resolve_approval(self, request_id: int, answer: str) -> None:
        self.sink.resolve_approval(answer)

    def clear(self) -> None:
        self.engine.clear()

    def compact(self) -> None:
        self.engine.compact()

    def get_todos(self) -> str:
        return self.engine.render_todos()

    def list_tools(self) -> list[dict[str, str]]:
        return [{"name": n, "description": d} for n, d in self.engine.list_tools()]

    def get_config(self) -> dict[str, Any]:
        return self.engine.get_config()

    def save_config(
        self,
        model: str,
        api_base: str,
        api_key: str,
        auto_approve: bool,
    ) -> dict[str, Any]:
        key_arg = api_key if api_key else None
        self.engine.set_config(
            model=model,
            api_base=api_base,
            api_key=key_arg,
            auto_approve=auto_approve,
        )
        storage.save_config(
            {"model": model, "api_base": api_base, "auto_approve": auto_approve}
        )
        if api_key:
            storage.set_api_key(api_key)
        return self.engine.get_config()


def main() -> None:
    import webview

    api = Api()
    index = _frontend_dir() / "index.html"
    window = webview.create_window(
        title=f"{APP_NAME} {__version__}",
        url=str(index),
        js_api=api,
        width=1100,
        height=760,
        min_size=(760, 560),
    )
    api.bind_window(window)
    webview.start()


if __name__ == "__main__":
    main()
