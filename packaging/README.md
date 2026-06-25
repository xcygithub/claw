# 打包 LegalClaw 桌面应用

把 Python 应用打成 `LegalClaw-0.2.0-Setup.exe` 的完整流程(Windows)。

## 前置

```powershell
pip install -e ".[desktop,build]"
```

这会装上运行所需的 `pywebview` 和打包用的 `pyinstaller`。

## 步骤 1: 用 PyInstaller 生成 exe

在仓库根目录执行:

```powershell
pyinstaller packaging/LegalClaw.spec
```

产物在 `dist/LegalClaw/LegalClaw.exe`(one-folder 形式, 整个文件夹是一个应用)。
可先双击它确认能正常启动。

可选: 把应用图标放到 `packaging/icon.ico`, spec 会自动使用。

## 步骤 2: 用 Inno Setup 生成安装包

1. 安装 [Inno Setup](https://jrsoftware.org/isinfo.php)
2. 编译脚本:

```powershell
iscc packaging/installer.iss
```

产物: `dist/LegalClaw-0.2.0-Setup.exe`，含开始菜单/桌面快捷方式与卸载器。

## 注意事项

- **WebView2 运行时**: Win11 内置; 部分 Win10 缺失。安装器会检测并提示用户安装
  Evergreen Bootstrapper(可改为静默下载)。
- **隐藏导入**: `litellm` 按需导入多, spec 里已用 `collect_submodules`/`collect_data_files`
  收集; 若运行时报 `ModuleNotFoundError`, 在 spec 的 `hiddenimports` 里补上。
- **杀软/SmartScreen**: 未做代码签名的 exe 会触发"未知发布者"警告, 也可能被杀软误报。
  正式分发建议购买代码签名证书并对 exe 与 Setup 签名。
- **用户数据**: 配置存于 `%APPDATA%\LegalClaw\config.json`, API Key 存于 Windows 凭据管理器。
