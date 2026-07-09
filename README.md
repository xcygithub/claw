# LegalClaw

一个用 Python 实现的多模型 AI 助手，提供两种形态：

- `claw`：终端 CLI Agent（类似 Claude Code / Cursor Agent）
- `legalclaw`：Windows 桌面应用（pywebview + Web 界面），可打包成 `LegalClaw-0.2.0-Setup.exe`

两者共用同一个 Python 核心（引擎 / 工具 / 记忆 / 任务编排）。

## 特性

- 多模型可切换：基于 [litellm](https://github.com/BerriAI/litellm)，支持 OpenAI、Anthropic、Ollama 及任意 OpenAI 兼容服务
- 工具调用循环：自主决定调用 `read_file` / `edit_file` / `run_command` / `grep` 等工具
- 安全确认：写文件、执行命令默认需确认；高危命令（如 `rm -rf`）强提醒
- 任务编排（L1）：
  - 计划与 TODO 清单：复杂任务先用 `write_todos` 列计划，推进时更新状态，`/todos` 可查看
  - 工具并行：同一轮内多个独立工具调用会并发执行（如同时读多个文件），明显提速
- 记忆系统：
  - 分层记忆：项目记忆 `CLAW.md`（当前项目）+ 全局记忆 `GLOBAL.md`（跨项目的个人偏好/常用命令），
    agent 可用 `update_memory` 主动写入，条目带标签/重要性/来源，仍是可直接用文本编辑器打开的 Markdown
  - 检索：记忆较多时只把高优先级摘要注入系统提示词，agent 可用 `search_memory` 按关键词检索完整记忆
  - 自动提取：压缩/清空历史前自动从对话里提炼候选记忆并去重写入，减少"忘记手动记录"导致的丢失
  - 会话持久化：对话自动落盘，`/resume` 或启动参数 `--continue`/`-c` 可恢复上次会话
  - 上下文压缩：历史接近上限时自动摘要，支持 `/compact` 手动触发
  - 桌面端有独立的"记忆"面板：查看/搜索/编辑/删除记忆条目、浏览并恢复历史会话
- 界面无关核心：Agent 通过 `EventSink` 事件接口输出，终端用 rich 渲染，桌面用流式 Web UI
- 桌面化存储：配置存 `%APPDATA%\LegalClaw\config.json`，API Key 存 Windows 凭据管理器（keyring）

## 桌面应用

```bash
pip install -e ".[desktop]"
python -m claw.app      # 或安装后运行 legalclaw
```

打包成 `Setup.exe` 的完整流程见 [packaging/README.md](packaging/README.md)（PyInstaller + Inno Setup）。

架构：前端 Web 界面 ←(pywebview JS 桥)→ `claw/app.py` 的 `Api` ←→ `ClawEngine` 核心。
流式输出、工具调用可视化、确认弹窗、设置页（模型 / api_base / key / 自动批准）均在 GUI 内完成。

## 安装

需要 Python 3.10+。

```bash
pip install -e .
```

## 配置

复制 `.env.example` 为 `.env`，填入对应厂商的 API Key：

```bash
cp .env.example .env
```

关键环境变量：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | 对应官方厂商密钥 | - |
| `CLAW_MODEL` | litellm 模型标识（注意前缀，见下） | `gpt-4o` |
| `CLAW_API_BASE` | 自定义端点地址（中转 / 兼容模式 / 本地） | - |
| `CLAW_API_KEY` | 配合 `CLAW_API_BASE` 使用的 key | - |
| `CLAW_AUTO_APPROVE` | 自动批准所有工具调用 | `false` |
| `CLAW_MAX_ITERATIONS` | 单轮最大工具迭代数 | `25` |
| `CLAW_COMPACT_THRESHOLD` | 触发压缩的上下文占比 | `0.7` |
| `CLAW_MEMORY_FILE` | 项目记忆文件名 | `CLAW.md` |
| `CLAW_MEMORY_GLOBAL_FILE` | 全局记忆文件路径，留空则用数据目录下的 `GLOBAL.md` | - |
| `CLAW_MEMORY_DIGEST_CHARS` | 注入系统提示词的记忆摘要最大字符数 | `4000` |
| `CLAW_AUTO_MEMORY_EXTRACT` | 压缩/清空历史前是否自动提取候选记忆 | `true` |
| `CLAW_SESSION_PERSIST` | 是否持久化对话以支持 `/resume` | `true` |

## 接入第三方 / 国产模型（OpenAI 兼容端点）

litellm 用 `CLAW_MODEL` 里 `/` 前面的前缀决定调用哪家服务，这一点最容易踩坑。

要走「自定义 base_url 的 OpenAI 兼容端点」（第三方中转、阿里百炼兼容模式、本地 vLLM 等），
模型必须用 `openai/` 前缀，并配 `CLAW_API_BASE` + `CLAW_API_KEY`：

```bash
# 例: 通过阿里 dashscope(百炼)兼容接口调用其上托管的 MiniMax 模型
CLAW_MODEL=openai/MiniMax-M2.7
CLAW_API_KEY=sk-xxx
CLAW_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
```

`openai/` 后面填服务端实际的模型 id（以平台控制台为准）。也可用厂商原生 provider，
如 Qwen 原生：`CLAW_MODEL=dashscope/qwen-plus` + `DASHSCOPE_API_KEY`。

### 常见报错排查

| 报错 | 原因 | 解决 |
| --- | --- | --- |
| `Missing credentials. Please pass the API key` | 模型前缀写成了具体厂商名（如 `MiniMax/...`），litellm 路由到该厂商 provider 却找不到对应 key | 改用 `openai/` 前缀 + `CLAW_API_BASE`/`CLAW_API_KEY` |
| `LLM Provider NOT provided` | 模型名没有前缀（如 `qwen-plus`） | 加前缀，如 `openai/qwen-plus` 或 `dashscope/qwen-plus` |
| `401 / 403` | key 无效或区域不对 | 核对 key；国内用 `dashscope.aliyuncs.com`，国际用 `dashscope-intl.aliyuncs.com` |
| `404 / 连接错误` | `CLAW_API_BASE` 缺失或地址错误 | 补全兼容端点地址（通常以 `/v1` 结尾） |
| `model not found` | 模型 id 在该平台不存在 | 用平台控制台列出的准确模型 id |

## 使用

交互式：

```bash
claw
# 或
python -m claw
```

单次任务：

```bash
claw "为 utils.py 里的 parse_date 函数补充单元测试"
```

恢复上次会话继续对话：

```bash
claw --continue
# 或
claw -c
```

### 交互命令

| 命令 | 说明 |
| --- | --- |
| `/model <名称>` | 切换模型，如 `/model anthropic/claude-3-5-sonnet-20241022` |
| `/tools` | 列出已注册工具 |
| `/todos` | 显示当前任务清单 |
| `/clear` | 清空对话历史(清空前会自动提取一次候选记忆) |
| `/compact` | 手动压缩对话历史(压缩前同样会自动提取记忆) |
| `/memory` | 列出全部记忆条目(项目 CLAW.md + 全局 GLOBAL.md) |
| `/memory search <关键词>` | 按关键词检索记忆 |
| `/memory forget <id>` | 删除指定 id 的记忆条目 |
| `/resume` | 列出可恢复的历史会话 |
| `/resume <序号>` | 恢复对应的历史会话，继续上次对话 |
| `/help` | 帮助 |
| `/exit` | 退出 |

## 项目结构

```
claw/
  cli.py          REPL 与单次模式入口
  agent.py        工具调用主循环
  config.py       配置加载
  messages.py     会话历史
  memory.py       上下文压缩(自动摘要) + 对话转写(compact/extract 共用)
  memory_store.py 结构化记忆存储: 分层(项目/全局)解析/检索/摘要
  memory_extract.py 自动记忆提取: 压缩/清空前从对话中提炼候选记忆并去重写入
  prompts.py      系统提示词
  safety.py       危险操作确认
  ui.py           rich 终端渲染
  todos.py        任务清单(TODO)状态
  llm/client.py   litellm 封装(含流式 complete_stream)
  core/
    events.py     EventSink 事件接口(界面无关)
    console_sink.py 终端事件渲染
    engine.py     会话引擎门面(CLI/GUI 共用)
    storage.py    数据目录 + 配置 + keyring 密钥 + 记忆/会话路径
    session_store.py 会话持久化(按项目分桶的 JSON 快照, 供 /resume 恢复)
  tools/          write_todos/read/write/edit/list/grep/glob/run_command/update_memory/search_memory
app.py            pywebview 桌面入口 + Api 桥接(含记忆面板/会话恢复接口) + WebEventSink
frontend/         Web 前端(index.html / app.js / markdown.js / styles.css), 含记忆管理弹窗
packaging/        LegalClaw.spec (PyInstaller) + installer.iss (Inno Setup)
```

## 许可证

MIT
