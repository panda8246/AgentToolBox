#!/usr/bin/env python3
"""Goal Framework documents, parsing, and safe file operations."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

STATE_FILE = ".goal-framework.json"
LOCK_FILE = ".goal-framework.lock"
START_MARKER = "<!-- GOAL-FRAMEWORK:START -->"
END_MARKER = "<!-- GOAL-FRAMEWORK:END -->"
FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CHECK_RE = re.compile(r"^- \[([ xX])\] (.+)$")
LINK_RE = re.compile(r"\]\(\.\./goals/active/([^)]+\.md)\)")
TECHNICAL_PLAN_LINK_RE = re.compile(
    r"^- \[(?P<label>(?:\\.|[^\]])+)\]\((?P<target>[^()\s]+)\)$"
)

GOAL_HEADINGS = ("目的", "完成条件", "当前进度", "下一步", "结果与归档")
TECHNICAL_PLAN_HEADING = "技术方案"
TECHNICAL_PLANS_DIR = Path("docs") / "technical-plans"
VALID_TYPES = {"delivery": "交付型", "exploration": "探索型"}
VALID_STATUSES = {"待开始", "进行中", "阻塞", "已完成"}


class GoalFrameworkError(RuntimeError):
    """A user-correctable framework error."""


def today_iso() -> str:
    return datetime.now().astimezone().date().isoformat()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise GoalFrameworkError(f"缺少文件：{path}") from exc
    except UnicodeDecodeError as exc:
        raise GoalFrameworkError(f"文件不是有效 UTF-8：{path}") from exc


def atomic_write(path: Path, content: str) -> None:
    """Write UTF-8 content through a same-directory temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as handle:
            handle.write(content.rstrip() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


class ProjectLock:
    """Fail fast when another process may be changing framework files."""

    def __init__(self, root: Path):
        self.path = root / LOCK_FILE
        self._acquired = False

    def __enter__(self) -> ProjectLock:  # noqa: PYI034 - keep Python 3.10 compatibility
        payload = (
            f"pid={os.getpid()} acquired={datetime.now().astimezone().isoformat()}\n"
        )
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise GoalFrameworkError(
                f"检测到写入锁 {self.path}。确认没有其他进程操作后再删除陈旧锁。"
            ) from exc
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        self._acquired = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


class FileTransaction:
    """Apply a few file operations and restore their snapshots on failure."""

    def __init__(self) -> None:
        self._writes: dict[Path, str] = {}
        self._deletes: set[Path] = set()

    def write(self, path: Path, content: str) -> None:
        self._writes[path] = content
        self._deletes.discard(path)

    def delete(self, path: Path) -> None:
        self._deletes.add(path)
        self._writes.pop(path, None)

    def commit(self) -> None:
        targets = set(self._writes) | self._deletes
        snapshots = {
            path: path.read_bytes() if path.exists() else None for path in targets
        }
        try:
            for path, content in self._writes.items():
                atomic_write(path, content)
            for path in self._deletes:
                path.unlink()
        except Exception:
            for path, snapshot in snapshots.items():
                if snapshot is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(snapshot)
            raise


def validate_date(value: str, label: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise GoalFrameworkError(f"{label} 不是有效日期：{value}") from exc


def section_span(text: str, heading: str) -> tuple[int, int, int]:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise GoalFrameworkError(
            f"应且只能有一个二级标题“{heading}”，实际为 {len(matches)} 个。"
        )
    match = matches[0]
    next_heading = re.search(r"^## .+$", text[match.end() :], re.MULTILINE)
    body_end = match.end() + next_heading.start() if next_heading else len(text)
    return match.start(), match.end(), body_end


def section_body(text: str, heading: str) -> str:
    _, body_start, body_end = section_span(text, heading)
    return text[body_start:body_end].strip()


def replace_section(text: str, heading: str, body: str) -> str:
    heading_start, _, body_end = section_span(text, heading)
    replacement = f"## {heading}\n\n{body.strip()}\n\n"
    return (
        text[:heading_start].rstrip() + "\n\n" + replacement + text[body_end:].lstrip()
    )


def replace_metadata(text: str, label: str, value: str, *, add: bool = False) -> str:
    pattern = re.compile(rf"^- {re.escape(label)}：.*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    replacement = f"- {label}：{value}"
    if len(matches) == 1:
        return pattern.sub(replacement, text, count=1)
    if matches:
        raise GoalFrameworkError(f"元数据“{label}”出现多次。")
    if not add:
        raise GoalFrameworkError(f"缺少元数据“{label}”。")
    first_heading = re.search(r"^## ", text, re.MULTILINE)
    if not first_heading:
        raise GoalFrameworkError("目标文件缺少二级标题。")
    prefix = text[: first_heading.start()].rstrip()
    return prefix + f"\n{replacement}\n\n" + text[first_heading.start() :]


def metadata(text: str, label: str, *, required: bool = True) -> str | None:
    matches = re.findall(rf"^- {re.escape(label)}：\s*(.+?)\s*$", text, re.MULTILINE)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise GoalFrameworkError(f"元数据“{label}”出现多次。")
    if required:
        raise GoalFrameworkError(f"缺少元数据“{label}”。")
    return None


def markdown_title(text: str) -> str:
    matches = re.findall(r"^# (.+?)\s*$", text, re.MULTILINE)
    if len(matches) != 1:
        raise GoalFrameworkError("目标文件应且只能有一个一级标题。")
    return matches[0]


def checklist(text: str) -> list[tuple[bool, str]]:
    conditions: list[tuple[bool, str]] = []
    for line in section_body(text, "完成条件").splitlines():
        if not line.strip():
            continue
        match = CHECK_RE.fullmatch(line.strip())
        if not match:
            raise GoalFrameworkError(f"完成条件必须使用复选框：{line.strip()}")
        conditions.append((match.group(1).lower() == "x", match.group(2).strip()))
    if not conditions:
        raise GoalFrameworkError("至少需要一个完成条件。")
    return conditions


def render_checklist(conditions: Sequence[tuple[bool, str]]) -> str:
    return "\n".join(
        f"- [{'x' if checked else ' '}] {text}" for checked, text in conditions
    )


@dataclass(frozen=True)
class TechnicalPlanLink:
    label: str
    target: str


def technical_plan_links(text: str) -> list[TechnicalPlanLink]:
    matches = list(
        re.finditer(
            rf"^## {re.escape(TECHNICAL_PLAN_HEADING)}\s*$", text, re.MULTILINE
        )
    )
    if not matches:
        return []
    if len(matches) > 1:
        raise GoalFrameworkError(
            f"应最多有一个二级标题“{TECHNICAL_PLAN_HEADING}”，实际为 {len(matches)} 个。"
        )
    body = section_body(text, TECHNICAL_PLAN_HEADING)
    content_lines = [
        line.strip()
        for line in body.splitlines()
        if line.strip()
        and not (line.strip().startswith("<!--") and line.strip().endswith("-->"))
    ]
    if not content_lines or content_lines in (["暂无。"], ["暂无"]):
        return []
    links: list[TechnicalPlanLink] = []
    for line in content_lines:
        match = TECHNICAL_PLAN_LINK_RE.fullmatch(line)
        if not match:
            raise GoalFrameworkError(
                f"技术方案必须使用 Markdown 链接列表或“暂无。”：{line}"
            )
        links.append(
            TechnicalPlanLink(
                label=match.group("label"), target=match.group("target")
            )
        )
    return links


def render_technical_plan_links(links: Sequence[TechnicalPlanLink]) -> str:
    if not links:
        return "暂无。"
    return "\n".join(f"- [{link.label}]({link.target})" for link in links)


def replace_technical_plan_links(
    text: str, links: Sequence[TechnicalPlanLink]
) -> str:
    body = render_technical_plan_links(links)
    matches = list(
        re.finditer(
            rf"^## {re.escape(TECHNICAL_PLAN_HEADING)}\s*$", text, re.MULTILINE
        )
    )
    if len(matches) == 1:
        return replace_section(text, TECHNICAL_PLAN_HEADING, body)
    if len(matches) > 1:
        raise GoalFrameworkError(
            f"应最多有一个二级标题“{TECHNICAL_PLAN_HEADING}”，实际为 {len(matches)} 个。"
        )
    progress_start, _, _ = section_span(text, "当前进度")
    return (
        text[:progress_start].rstrip()
        + f"\n\n## {TECHNICAL_PLAN_HEADING}\n\n{body}\n\n"
        + text[progress_start:].lstrip()
    )


def parse_subsection_bullets(body: str, heading: str) -> list[str]:
    pattern = re.compile(rf"^### {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return []
    next_heading = re.search(r"^### .+$", body[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(body)
    items: list[str] = []
    for line in body[match.end() : end].splitlines():
        item = re.match(r"^-\s+(.+)$", line.strip())
        if item and item.group(1) not in {"暂无。", "暂无"}:
            items.append(item.group(1).strip())
    return items


def parse_numbered_items(body: str) -> list[str]:
    items: list[str] = []
    for line in body.splitlines():
        match = re.match(r"^\d+\.\s+(.+)$", line.strip())
        if match:
            items.append(match.group(1).strip())
    return items


def render_progress(
    done: Sequence[str], current: Sequence[str], blocked: Sequence[str]
) -> str:
    def bullets(values: Sequence[str]) -> str:
        return "\n".join(f"- {value}" for value in values) if values else "- 暂无。"

    return (
        f"### 已完成\n\n{bullets(done)}\n\n"
        f"### 进行中\n\n{bullets(current)}\n\n"
        f"### 待确认 / 阻塞\n\n{bullets(blocked)}"
    )


def render_next(values: Sequence[str]) -> str:
    if not values:
        return "暂无。"
    return "\n".join(f"{index}. {value}" for index, value in enumerate(values, 1))


@dataclass
class GoalDocument:
    path: Path
    text: str
    title: str
    goal_type: str
    status: str
    created: str
    updated: str
    archived: str | None
    conditions: list[tuple[bool, str]]
    technical_plans: list[TechnicalPlanLink]

    @classmethod
    def load(cls, path: Path) -> GoalDocument:
        return cls.from_text(path, read_text(path))

    @classmethod
    def from_text(cls, path: Path, text: str) -> GoalDocument:
        for heading in GOAL_HEADINGS:
            section_span(text, heading)
        return cls(
            path=path,
            text=text,
            title=markdown_title(text),
            goal_type=metadata(text, "类型") or "",
            status=metadata(text, "状态") or "",
            created=metadata(text, "创建日期") or "",
            updated=metadata(text, "最近更新") or "",
            archived=metadata(text, "归档日期", required=False),
            conditions=checklist(text),
            technical_plans=technical_plan_links(text),
        )


@dataclass
class Project:
    root: Path
    current_path: Path = field(init=False)
    active_dir: Path = field(init=False)
    archive_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root = self.root.expanduser().resolve()
        self.current_path = self.root / "docs" / "CURRENT.md"
        self.active_dir = self.root / "goals" / "active"
        self.archive_dir = self.root / "goals" / "archive"

    def require_initialized(self) -> None:
        if not self.root.is_dir():
            raise GoalFrameworkError(f"项目目录不存在：{self.root}")
        required = (
            self.root / STATE_FILE,
            self.current_path,
            self.active_dir,
            self.archive_dir,
        )
        for path in required:
            if not path.exists():
                raise GoalFrameworkError(f"项目未完整初始化，缺少：{path}")

    def active_goals(self) -> list[GoalDocument]:
        return [
            GoalDocument.load(path) for path in sorted(self.active_dir.glob("*.md"))
        ]

    def resolve_active(self, reference: str) -> GoalDocument:
        name = Path(reference).name
        exact = self.active_dir / name
        if exact.is_file():
            return GoalDocument.load(exact)
        matches = [goal for goal in self.active_goals() if reference in goal.path.stem]
        if not matches:
            raise GoalFrameworkError(f"找不到活跃目标：{reference}")
        if len(matches) > 1:
            names = "、".join(goal.path.name for goal in matches)
            raise GoalFrameworkError(f"目标引用不唯一：{reference}；匹配 {names}")
        return matches[0]


def render_goal(
    *, title: str, goal_type: str, purpose: str, conditions: Sequence[str], created: str
) -> str:
    unchecked = [(False, condition) for condition in conditions]
    return f"""# {title}

- 类型：{goal_type}
- 状态：待开始
- 创建日期：{created}
- 最近更新：{created}

## 目的

{purpose}

## 完成条件

{render_checklist(unchecked)}

## 技术方案

暂无。

## 当前进度

{render_progress([], [], [])}

## 下一步

暂无。

## 结果与归档

尚未完成。
"""


def update_current(text: str, goals: Sequence[GoalDocument], updated: str) -> str:
    if not re.search(r"^- 最后更新：.*$", text, re.MULTILINE):
        raise GoalFrameworkError("CURRENT.md 缺少“最后更新”字段。")
    text = re.sub(
        r"^- 最后更新：.*$", f"- 最后更新：{updated}", text, count=1, flags=re.MULTILINE
    )
    if goals:
        body = "\n".join(
            f"- [{goal.title}](../goals/active/{goal.path.name}) — {goal.status}"
            for goal in goals
        )
    else:
        body = "- 暂无。需要时在 `goals/active/` 创建目标文件。"
    return replace_section(text, "活跃目标", body)
