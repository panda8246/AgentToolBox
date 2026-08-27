#!/usr/bin/env python3
"""Shared functions for Goal Framework commands."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = FRAMEWORK_ROOT / "templates"
START_MARKER = "<!-- GOAL-FRAMEWORK:START -->"
END_MARKER = "<!-- GOAL-FRAMEWORK:END -->"
STATE_FILE = ".goal-framework.json"
SKILLS_ROOT = FRAMEWORK_ROOT / "skills"
PROJECT_SKILLS_ROOT = Path(".agents") / "skills"
MANAGED_SKILLS = ("goal-framework-operator",)
PYTHON_BYTECODE_GITIGNORE_RULES = (
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*$py.class",
)


def framework_version() -> str:
    return (FRAMEWORK_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def migrations() -> list[dict]:
    return json.loads(
        (FRAMEWORK_ROOT / "MIGRATIONS.json").read_text(encoding="utf-8-sig")
    )["releases"]


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
    section = (
        (TEMPLATES / "goal-framework-agents-section.md")
        .read_text(encoding="utf-8")
        .strip()
    )
    block = f"{START_MARKER}\n{section}\n{END_MARKER}\n"
    if dry_run:
        status("将创建或更新 AGENTS.md 中的 Goal Framework 受管区块。")
        return
    current = (
        agents_path.read_text(encoding="utf-8-sig")
        if agents_path.exists()
        else "# 项目 Agent 说明\n"
    )
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
    )
    if pattern.search(current):
        updated = pattern.sub(block.rstrip(), current).rstrip() + "\n"
        status("更新 AGENTS.md 中的 Goal Framework 受管区块。")
    else:
        updated = current.rstrip() + "\n\n" + block
        status("合并 Goal Framework 规则到 AGENTS.md。")
    agents_path.write_text(updated, encoding="utf-8")


def ensure_python_bytecode_gitignore(project: Path, dry_run: bool) -> None:
    """Add missing Python bytecode ignore rules without changing user rules."""
    gitignore_path = project / ".gitignore"
    current = (
        gitignore_path.read_text(encoding="utf-8-sig") if gitignore_path.exists() else ""
    )
    existing_rules = {
        line.strip()
        for line in current.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing_rules = [
        rule for rule in PYTHON_BYTECODE_GITIGNORE_RULES if rule not in existing_rules
    ]
    if not missing_rules:
        status(".gitignore 已包含 Python 字节码忽略规则。")
        return

    status(f"更新 .gitignore：添加 {len(missing_rules)} 条 Python 字节码忽略规则。")
    if dry_run:
        return

    addition = "# Python bytecode caches\n" + "\n".join(missing_rules) + "\n"
    separator = "" if not current else ("\n" if current.endswith("\n") else "\n\n")
    gitignore_path.write_text(current + separator + addition, encoding="utf-8")


def copy_template(
    project: Path, relative_path: str, force: bool, dry_run: bool
) -> None:
    source = TEMPLATES / relative_path
    target = project / relative_path
    if target.exists() and not force:
        status(f"保留已有文件：{relative_path}")
        return
    status(f"写入模板：{relative_path}")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def ignored_skill_path(relative: Path) -> bool:
    """Return whether a path is generated Python bytecode, never managed by the framework."""
    return (
        "__pycache__" in relative.parts
        or relative.suffix.lower() in {".pyc", ".pyo"}
        or relative.name.endswith("$py.class")
    )


def distributable_skill_files(skill_name: str) -> list[Path]:
    """Return runtime files for a bundled skill, excluding its development tests."""
    skill_root = SKILLS_ROOT / skill_name
    if not skill_root.is_dir():
        raise ValueError(f"框架缺少受管 skill：{skill_name}")
    files: list[Path] = []
    for path in skill_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(skill_root)
        if "tests" in relative.parts or ignored_skill_path(relative):
            continue
        files.append(relative)
    return sorted(files, key=lambda path: path.as_posix())


def skill_state() -> dict[str, dict[str, object]]:
    return {
        name: {
            "version": framework_version(),
            "files": [path.as_posix() for path in distributable_skill_files(name)],
        }
        for name in MANAGED_SKILLS
    }


def safe_skill_target(project: Path, skill_name: str, relative: Path) -> Path:
    target_root = project / PROJECT_SKILLS_ROOT / skill_name
    target = target_root / relative
    resolved_project = project.resolve()
    resolved_parent = target.parent.resolve()
    if not resolved_parent.is_relative_to(resolved_project):
        raise ValueError(f"skill 目标路径越出项目目录：{target}")
    if target.is_symlink():
        raise ValueError(f"拒绝覆盖符号链接形式的受管 skill 文件：{target}")
    return target


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def sync_project_skills(project: Path, dry_run: bool = False) -> None:
    """Install managed skill runtime files while preserving unrelated user files."""
    previous_state = read_state(project) or {}
    previous_skills = previous_state.get("skills", {})
    if not isinstance(previous_skills, dict):
        previous_skills = {}

    for skill_name in MANAGED_SKILLS:
        source_root = SKILLS_ROOT / skill_name
        current_files = distributable_skill_files(skill_name)
        target_root = project / PROJECT_SKILLS_ROOT / skill_name
        action = "更新" if target_root.exists() else "安装"
        status(f"{action}项目 skill：{PROJECT_SKILLS_ROOT / skill_name}")
        if dry_run:
            continue

        for relative in current_files:
            target = safe_skill_target(project, skill_name, relative)
            atomic_copy(source_root / relative, target)

        previous = previous_skills.get(skill_name, {})
        previous_files = previous.get("files", []) if isinstance(previous, dict) else []
        if not isinstance(previous_files, list):
            previous_files = []
        stale_files = {
            str(path)
            for path in previous_files
            if not ignored_skill_path(Path(str(path)))
        } - {path.as_posix() for path in current_files}
        for stale in sorted(stale_files):
            relative = Path(stale)
            target = safe_skill_target(project, skill_name, relative)
            if target.is_file():
                target.unlink()

        if target_root.is_dir():
            directories = sorted(
                (
                    path
                    for path in target_root.rglob("*")
                    if path.is_dir()
                    and "__pycache__" not in path.relative_to(target_root).parts
                ),
                key=lambda path: len(path.parts),
                reverse=True,
            )
            for directory in directories:
                try:
                    directory.rmdir()
                except OSError:
                    pass


def write_state(
    project: Path, initialized_at: str | None = None, dry_run: bool = False
) -> None:
    path = project / STATE_FILE
    existing = read_state(project) or {}
    current_date = datetime.now().astimezone().date().isoformat()
    state = {
        "version": framework_version(),
        "initializedAt": existing.get("initializedAt")
        or initialized_at
        or current_date,
        "updatedAt": current_date,
        "skills": skill_state(),
    }
    if dry_run:
        status(f"将更新 {STATE_FILE} 至版本 {state['version']}。")
        return
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_state(project: Path) -> dict | None:
    path = project / STATE_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{STATE_FILE} 格式无效：{exc}") from exc
