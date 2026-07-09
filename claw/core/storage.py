"""桌面化存储: 用户数据目录、配置文件(JSON)、密钥(系统钥匙串)。

CLI 仍可用 .env / 环境变量; GUI 则把配置存到 %APPDATA%\\LegalClaw\\config.json,
API key 存到操作系统的凭据管理器(通过 keyring), 不再让用户手改文件。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import platformdirs

from claw import APP_NAME

_KEYRING_SERVICE = APP_NAME
_API_KEY_ENTRY = "api_key"


def data_dir() -> Path:
    """返回用户数据目录(自动创建)。"""
    path = Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return data_dir() / "config.json"


def memory_path() -> Path:
    """GUI 模式下项目记忆文件落在数据目录。"""
    return data_dir() / "CLAW.md"


def global_memory_path() -> Path:
    """全局记忆文件(跨项目共享的个人偏好/常用命令), CLI 与桌面端共用。"""
    return data_dir() / "GLOBAL.md"


def sessions_dir() -> Path:
    """会话快照根目录, 按项目路径分子目录存放。"""
    path = data_dir() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_config(config: dict[str, Any]) -> None:
    config_path().write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_api_key() -> str | None:
    try:
        import keyring

        return keyring.get_password(_KEYRING_SERVICE, _API_KEY_ENTRY)
    except Exception:  # noqa: BLE001 - 某些环境无可用后端
        return None


def set_api_key(value: str | None) -> bool:
    """保存或清除 API key。返回是否成功。"""
    try:
        import keyring

        if value:
            keyring.set_password(_KEYRING_SERVICE, _API_KEY_ENTRY, value)
        else:
            try:
                keyring.delete_password(_KEYRING_SERVICE, _API_KEY_ENTRY)
            except Exception:  # noqa: BLE001 - 不存在时忽略
                pass
        return True
    except Exception:  # noqa: BLE001
        return False
