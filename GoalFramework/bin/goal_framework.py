#!/usr/bin/env python3
"""Shared functions for Goal Framework commands."""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = FRAMEWORK_ROOT / "templates"
START_MARKER = "<!-- GOAL-FRAMEWORK:START -->"
END_MARKER = "<!-- GOAL-FRAMEWORK:END -->"
STATE_FILE = ".goal-framework.json"


def framework_version() -> str:
    return (FRAMEWORK_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def migrations() -> list[dict]:
    return json.loads((FRAMEWORK_ROOT / "MIGRATIONS.json").read_text(encoding="utf-8-sig"))["releases"]


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def status(message: str) -> None:
    print(f"[goal-framework] {message}")


def warn(message: str) -> None:
    print(f"[goal-framework] 警告：{message}")


def commands() -> dict[str, str | None]:
    return {
        "codex": shutil.which("codex"),
        "cursor": shutil.which("cursor-agent") or shutil.which("cursor"),
        "opencode": shutil.which("opencode"),
    }


def merge_agents_section(project: Path, dry_run: bool) -> None:
    agents_path = project / "AGENTS.md"
    section = (TEMPLATES / "goal-framework-agents-section.md").read_text(encoding="utf-8").strip()
    block = f"{START_MARKER}\n{section}\n{END_MARKER}\n"
    if dry_run:
        status("将创建或更新 AGENTS.md 中的 Goal Framework 受管区块。")
        return
    current = agents_path.read_text(encoding="utf-8-sig") if agents_path.exists() else "# 项目 Agent 说明\n"
    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
    if pattern.search(current):
        updated = pattern.sub(block.rstrip(), current).rstrip() + "\n"
        status("更新 AGENTS.md 中的 Goal Framework 受管区块。")
    else:
        updated = current.rstrip() + "\n\n" + block
        status("合并 Goal Framework 规则到 AGENTS.md。")
    agents_path.write_text(updated, encoding="utf-8")


def copy_template(project: Path, relative_path: str, force: bool, dry_run: bool) -> None:
    source = TEMPLATES / relative_path
    target = project / relative_path
    if target.exists() and not force:
        status(f"保留已有文件：{relative_path}")
        return
    status(f"写入模板：{relative_path}")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def write_state(project: Path, initialized_at: str | None = None, dry_run: bool = False) -> None:
    path = project / STATE_FILE
    existing = read_state(project) or {}
    state = {
        "version": framework_version(),
        "initializedAt": existing.get("initializedAt") or initialized_at or date.today().isoformat(),
        "updatedAt": date.today().isoformat(),
    }
    if dry_run:
        status(f"将更新 {STATE_FILE} 至版本 {state['version']}。")
        return
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_state(project: Path) -> dict | None:
    path = project / STATE_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{STATE_FILE} 格式无效：{exc}") from exc


