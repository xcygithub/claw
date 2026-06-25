"""安全机制: 对有副作用的工具调用进行确认, 拦截危险命令。"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 高危命令模式(大小写不敏感), 命中时强提醒
DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\brmdir\s+/s\b",
    r"\bdel\s+/[sfq]",
    r"\bformat\b",
    r"\bmkfs\b",
    r":\(\)\s*\{",  # fork bomb
    r"\bdd\s+if=",
    r">\s*/dev/sd",
    r"\bgit\s+push\s+.*--force\b",
    r"\bshutdown\b",
    r"\breboot\b",
]


@dataclass
class ApprovalRequest:
    tool_name: str
    preview: str
    is_dangerous: bool


class SafetyManager:
    """决定某次工具调用是否需要用户确认。"""

    def __init__(self, auto_approve: bool = False) -> None:
        self.auto_approve = auto_approve
        # 用户在会话中选择"全部允许"后置为 True
        self._approve_all = False

    @staticmethod
    def is_dangerous_command(command: str) -> bool:
        return any(re.search(p, command, re.IGNORECASE) for p in DANGEROUS_PATTERNS)

    def needs_confirmation(self, tool_name: str, mutating: bool, command: str | None) -> bool:
        if mutating and command and self.is_dangerous_command(command):
            # 危险命令始终确认, 即便开启了 auto/approve_all
            return True
        if self.auto_approve or self._approve_all:
            return False
        return mutating

    def remember_approve_all(self) -> None:
        self._approve_all = True
