"""LegalClaw - 一个多模型 AI 助手 (CLI + Windows 桌面应用)。"""

import os as _os

# 必须在任何 pydantic / pydantic_settings 导入之前执行:
# 打包(PyInstaller)环境下, 第三方注册的 pydantic 插件(如 logfire)会调用
# inspect.getsource() 读取源码, 但冻结程序无源码文件, 会抛
# "OSError: could not get source code" 导致启动崩溃。禁用插件即可规避。
_os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")

__version__ = "0.2.0"
APP_NAME = "LegalClaw"
