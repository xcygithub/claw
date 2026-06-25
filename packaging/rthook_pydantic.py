"""PyInstaller 运行时钩子: 在任何模块导入前禁用 pydantic 第三方插件。

冻结环境下, logfire 等注册的 pydantic 插件会用 inspect.getsource 读取源码,
而打包程序没有 .py 源码, 触发 "OSError: could not get source code" 崩溃。
该钩子由 PyInstaller 在最早期执行, 确保环境变量先于 pydantic 生效。
"""

import os

os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")
