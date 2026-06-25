"""配置加载: 从环境变量 / .env 读取运行时设置。"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Claw 运行时配置。

    所有字段均可通过环境变量(前缀 ``CLAW_``)或 ``.env`` 文件覆盖。
    """

    model_config = SettingsConfigDict(
        env_prefix="CLAW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = Field(default="gpt-4o", description="litellm 模型标识")
    api_base: str | None = Field(
        default=None,
        description="自定义 API 端点(OpenAI 兼容服务/中转/百炼兼容模式), 对应 CLAW_API_BASE",
    )
    api_key: str | None = Field(
        default=None,
        description="自定义 API key(配合 api_base 使用), 对应 CLAW_API_KEY",
    )
    auto_approve: bool = Field(default=False, description="是否自动批准所有工具调用")
    max_iterations: int = Field(default=25, description="单轮回复最大工具迭代次数")
    compact_threshold: float = Field(
        default=0.7, description="触发上下文压缩的 token 占比阈值 (0-1)"
    )
    memory_file: str = Field(default="CLAW.md", description="项目记忆文件名")
    max_tool_output_chars: int = Field(
        default=20000, description="单个工具输出的最大字符数, 超出则截断"
    )
    max_parallel_tools: int = Field(
        default=8, description="单轮内并行执行工具的最大并发数"
    )

    def context_window(self) -> int:
        """返回当前模型的上下文窗口大小(token), 失败则回退默认值。"""
        try:
            import litellm

            info = litellm.get_model_info(self.model)
            window = info.get("max_input_tokens") or info.get("max_tokens")
            if window:
                return int(window)
        except Exception:
            pass
        return 128_000


def load_settings() -> Settings:
    """加载配置。集中入口便于后续测试时替换。"""
    return Settings()
