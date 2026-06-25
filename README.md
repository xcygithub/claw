# Claw

一个用 Python 实现的多模型编程 CLI Agent，风格类似 Claude Code / Cursor Agent。
它在你的终端里运行，能自主读写文件、执行命令、搜索代码，循环完成编码任务。

## 特性

- 多模型可切换：基于 [litellm](https://github.com/BerriAI/litellm)，支持 OpenAI、Anthropic、Ollama 及任意 OpenAI 兼容服务
- 工具调用循环：自主决定调用 `read_file` / `edit_file` / `run_command` / `grep` 等工具
- 安全确认：写文件、执行命令默认需确认；高危命令（如 `rm -rf`）强提醒
- 记忆系统：
  - 项目记忆文件 `CLAW.md`：启动自动加载，agent 可用 `update_memory` 主动写入长期知识
  - 上下文压缩：历史接近上限时自动摘要，支持 `/compact` 手动触发
- 富终端 UI：基于 `rich` 渲染工具调用、结果与 Markdown 回复

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

### 交互命令

| 命令 | 说明 |
| --- | --- |
| `/model <名称>` | 切换模型，如 `/model anthropic/claude-3-5-sonnet-20241022` |
| `/tools` | 列出已注册工具 |
| `/clear` | 清空对话历史 |
| `/compact` | 手动压缩对话历史 |
| `/help` | 帮助 |
| `/exit` | 退出 |

## 项目结构

```
claw/
  cli.py          REPL 与单次模式入口
  agent.py        工具调用主循环
  config.py       配置加载
  messages.py     会话历史
  memory.py       项目记忆加载 + 上下文压缩
  prompts.py      系统提示词
  safety.py       危险操作确认
  ui.py           rich 终端渲染
  llm/client.py   litellm 封装
  tools/          read/write/edit/list/grep/glob/run_command/update_memory
```

## 许可证

MIT
