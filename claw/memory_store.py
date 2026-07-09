"""结构化记忆存储: 解析/序列化带元数据的 Markdown, 提供分层(项目/全局)读写与检索。

记忆仍然落在人可读的 ``.md`` 文件里(项目记忆 ``CLAW.md``、全局记忆 ``GLOBAL.md``),
只是每条 bullet 后面附带一段 ``<!--claw:...-->`` 元数据注释, 记录 id/标签/重要性/
来源/时间。对没有元数据的旧版纯文本 bullet 完全兼容(降级为默认字段), 用户仍可
直接用文本编辑器查看/修改这些文件。
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_DEFAULT_SECTION = "未分类"
_VALID_IMPORTANCE = ("low", "normal", "high")
_IMPORTANCE_ORDER = {"high": 0, "normal": 1, "low": 2}

_META_RE = re.compile(r"^<!--claw:(?P<meta>[^>]*)-->\s*(?P<content>.*)$")
_LEGACY_TS_RE = re.compile(r"^\((?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\)\s*(?P<rest>.*)$")

_TITLES = {
    "project": "项目记忆 (CLAW.md)",
    "global": "全局记忆 (GLOBAL.md)",
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def _stable_id(scope: str, section: str, content: str) -> str:
    """给没有显式 id 的旧条目算一个稳定 id(内容不变则每次加载一致)。"""
    digest = hashlib.sha1(f"{scope}|{section}|{content}".encode("utf-8")).hexdigest()
    return digest[:8]


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class MemoryEntry:
    """一条记忆条目。"""

    id: str
    content: str
    section: str = _DEFAULT_SECTION
    tags: list[str] = field(default_factory=list)
    importance: str = "normal"
    source: str = "manual"  # manual(agent/用户主动写入) / auto(自动提取)
    scope: str = "project"  # project / global
    created_at: str = ""
    updated_at: str = ""

    def matches(self, tokens: list[str]) -> int:
        """按 token 命中次数打分, 命中标签额外加权。"""
        haystack = f"{self.section} {self.content}".lower()
        score = sum(haystack.count(t) for t in tokens)
        tag_lower = [t.lower() for t in self.tags]
        score += sum(3 for t in tokens if t in tag_lower)
        return score


def _parse_meta(meta_str: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for part in meta_str.split():
        if "=" in part:
            key, value = part.split("=", 1)
            meta[key.strip()] = value.strip()
    return meta


def _parse_file(path: Path, scope: str) -> list[MemoryEntry]:
    if not path.exists() or not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return []

    entries: list[MemoryEntry] = []
    section = _DEFAULT_SECTION
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip() or _DEFAULT_SECTION
            continue
        if not stripped.startswith("- "):
            continue
        body = stripped[2:].strip()
        if not body:
            continue

        match = _META_RE.match(body)
        if match:
            content = match.group("content").strip()
            if not content:
                continue
            meta = _parse_meta(match.group("meta"))
            tags = [t for t in meta.get("tags", "").split(",") if t]
            importance = meta.get("importance", "normal")
            if importance not in _VALID_IMPORTANCE:
                importance = "normal"
            entry_id = meta.get("id") or _stable_id(scope, section, content)
            created = meta.get("created", "")
            entries.append(
                MemoryEntry(
                    id=entry_id,
                    content=content,
                    section=section,
                    tags=tags,
                    importance=importance,
                    source=meta.get("source", "manual"),
                    scope=scope,
                    created_at=created,
                    updated_at=meta.get("updated", created),
                )
            )
            continue

        # 旧版格式: "- (2026-01-01 12:00) 内容", 或纯文本 bullet
        content = body
        created = ""
        legacy = _LEGACY_TS_RE.match(body)
        if legacy:
            # 元数据注释用空格分隔键值对, 时间戳里的空格会破坏解析, 统一换成 T
            created = legacy.group("ts").replace(" ", "T")
            content = legacy.group("rest").strip()
        if not content:
            continue
        entries.append(
            MemoryEntry(
                id=_stable_id(scope, section, content),
                content=content,
                section=section,
                tags=[],
                importance="normal",
                source="manual",
                scope=scope,
                created_at=created,
                updated_at=created,
            )
        )
    return entries


def _format_entry(entry: MemoryEntry) -> str:
    parts = [f"id={entry.id}"]
    if entry.tags:
        parts.append(f"tags={','.join(entry.tags)}")
    parts.append(f"importance={entry.importance}")
    parts.append(f"source={entry.source}")
    if entry.created_at:
        parts.append(f"created={entry.created_at}")
    if entry.updated_at:
        parts.append(f"updated={entry.updated_at}")
    meta = " ".join(parts)
    return f"- <!--claw:{meta}--> {entry.content}"


def render_full(entries: list[MemoryEntry], scope: str) -> str:
    """把一组条目渲染成完整的 Markdown 文件内容(按 section 分组, 保留原始顺序)。"""
    lines = [
        f"# {_TITLES.get(scope, '记忆')}",
        "",
        "由 Claw 维护, 记录跨会话的长期知识。",
        "",
    ]
    grouped: dict[str, list[MemoryEntry]] = {}
    order: list[str] = []
    for entry in entries:
        if entry.section not in grouped:
            grouped[entry.section] = []
            order.append(entry.section)
        grouped[entry.section].append(entry)

    for section in order:
        lines.append(f"## {section}")
        for entry in grouped[section]:
            lines.append(_format_entry(entry))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


class MemoryStore:
    """管理项目记忆(cwd 下的 ``CLAW.md``)与全局记忆(数据目录下的 ``GLOBAL.md``)。"""

    def __init__(self, project_path: str | Path, global_path: str | Path) -> None:
        self.project_path = Path(project_path)
        self.global_path = Path(global_path)
        self._project_entries: list[MemoryEntry] = []
        self._global_entries: list[MemoryEntry] = []
        self.reload()

    def reload(self) -> None:
        self._project_entries = _parse_file(self.project_path, "project")
        self._global_entries = _parse_file(self.global_path, "global")

    def _entries_for(self, scope: str) -> list[MemoryEntry]:
        return self._project_entries if scope == "project" else self._global_entries

    def _path_for(self, scope: str) -> Path:
        return self.project_path if scope == "project" else self.global_path

    def _save(self, scope: str) -> None:
        path = self._path_for(scope)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_full(self._entries_for(scope), scope), encoding="utf-8")

    def all(self, scope: str | None = None) -> list[MemoryEntry]:
        if scope == "project":
            return list(self._project_entries)
        if scope == "global":
            return list(self._global_entries)
        return [*self._project_entries, *self._global_entries]

    def count(self, scope: str | None = None) -> int:
        return len(self.all(scope))

    def add(
        self,
        content: str,
        section: str | None = None,
        tags: list[str] | None = None,
        importance: str = "normal",
        scope: str = "project",
        source: str = "manual",
    ) -> MemoryEntry:
        content = content.strip()
        if not content:
            raise ValueError("记忆内容不能为空")
        scope = scope if scope in ("project", "global") else "project"
        importance = importance if importance in _VALID_IMPORTANCE else "normal"
        now = _now()
        entry = MemoryEntry(
            id=_new_id(),
            content=content,
            section=(section or "").strip() or _DEFAULT_SECTION,
            tags=[t.strip() for t in (tags or []) if t.strip()],
            importance=importance,
            source=source,
            scope=scope,
            created_at=now,
            updated_at=now,
        )
        self._entries_for(scope).append(entry)
        self._save(scope)
        return entry

    def update(
        self,
        entry_id: str,
        content: str | None = None,
        section: str | None = None,
        tags: list[str] | None = None,
        importance: str | None = None,
    ) -> bool:
        for scope in ("project", "global"):
            for entry in self._entries_for(scope):
                if entry.id != entry_id:
                    continue
                if content is not None and content.strip():
                    entry.content = content.strip()
                if section is not None and section.strip():
                    entry.section = section.strip()
                if tags is not None:
                    entry.tags = [t.strip() for t in tags if t.strip()]
                if importance is not None and importance in _VALID_IMPORTANCE:
                    entry.importance = importance
                entry.updated_at = _now()
                self._save(scope)
                return True
        return False

    def delete(self, entry_id: str) -> bool:
        for scope in ("project", "global"):
            entries = self._entries_for(scope)
            for i, entry in enumerate(entries):
                if entry.id == entry_id:
                    del entries[i]
                    self._save(scope)
                    return True
        return False

    def search(
        self, query: str, scope: str | None = None, top_k: int = 8
    ) -> list[MemoryEntry]:
        tokens = [t for t in re.split(r"\s+", query.strip().lower()) if t]
        if not tokens:
            return []
        scored = [
            (entry.matches(tokens), entry) for entry in self.all(scope)
        ]
        scored = [(score, entry) for score, entry in scored if score > 0]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def render_digest(self, max_chars: int = 4000) -> str:
        """按重要性(高->低)与更新时间(新->旧)排序, 生成注入 system prompt 的摘要。

        超出 ``max_chars`` 的部分会被省略, 并提示可用 ``search_memory`` 检索。
        """
        entries = self.all()
        if not entries:
            return ""
        entries = sorted(entries, key=lambda e: e.updated_at, reverse=True)
        entries = sorted(
            entries, key=lambda e: _IMPORTANCE_ORDER.get(e.importance, 1)
        )

        lines: list[str] = []
        total = 0
        omitted = 0
        for entry in entries:
            scope_label = "全局" if entry.scope == "global" else "项目"
            line = f"- [{scope_label}/{entry.section}] {entry.content}"
            if total + len(line) + 1 > max_chars:
                omitted += 1
                continue
            lines.append(line)
            total += len(line) + 1

        text = "\n".join(lines)
        if omitted:
            text += (
                f"\n(还有 {omitted} 条记忆因长度限制未在此展示, "
                "需要时可调用 search_memory 工具检索。)"
            )
        return text

    def render_full(self, scope: str) -> str:
        return render_full(self._entries_for(scope), scope)
