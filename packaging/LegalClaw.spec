# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置: 把 LegalClaw 桌面应用打成 one-folder。

用法(在仓库根目录):
    pyinstaller packaging/LegalClaw.spec

产物: dist/LegalClaw/LegalClaw.exe
"""

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = os.path.abspath(os.getcwd())

# litellm 依赖大量按需导入与数据文件, 需显式收集以免运行时 ImportError
hiddenimports = (
    collect_submodules("litellm")
    + collect_submodules("keyring")
    + ["webview"]
)
datas = collect_data_files("litellm")
datas += [(os.path.join(ROOT, "frontend"), "frontend")]

icon_path = os.path.join(ROOT, "packaging", "icon.ico")
icon = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    [os.path.join(ROOT, "claw", "app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LegalClaw",
    console=False,           # 桌面应用, 不弹控制台
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="LegalClaw",
)
