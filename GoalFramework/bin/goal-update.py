#!/usr/bin/env python3
"""Update an initialized project to the current Goal Framework version."""

from __future__ import annotations

import argparse
from pathlib import Path

from goal_framework import (
    copy_template,
    framework_version,
    merge_agents_section,
    migrations,
    read_state,
    status,
    sync_project_skills,
    version_key,
    write_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update an initialized Goal Framework project."
    )
    parser.add_argument("--project-path", "-p", default=".")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--yes", action="store_true", help="Apply updates without confirmation."
    )
    return parser.parse_args()


def releases_between(current: str, latest: str) -> list[dict]:
    return [
        release
        for release in migrations()
        if version_key(current) < version_key(release["version"]) <= version_key(latest)
    ]


def print_migration_plan(releases: list[dict]) -> None:
    print("\n将应用以下框架变更：")
    for release in releases:
        print(f"\n{release['version']}")
        for change in release["changes"]:
            print(f"  - {change}")
        for action in release.get("manualActions", []):
            print(f"  - 需要留意：{action}")
    print(
        "\n自动更新：AGENTS.md 的受管区块、goals/GOAL-TEMPLATE.md、项目级 skill 与 .goal-framework.json。"
    )
    print(
        "绝不自动修改：docs/PROJECT.md、docs/CURRENT.md、docs/technical-plans/*、"
        "goals/active/*、goals/archive/*。"
    )


def main() -> int:
    args = parse_args()
    project = Path(args.project_path).expanduser().resolve()
    if not project.is_dir():
        raise SystemExit(f"项目目录不存在：{project}")
    try:
        state = read_state(project)
    except ValueError as exc:
        raise SystemExit(str(exc))
    if not state:
        raise SystemExit("未发现 .goal-framework.json。请先运行 goal-init。")
    current = state.get("version")
    latest = framework_version()
    if not current:
        raise SystemExit(".goal-framework.json 缺少 version。")
    if version_key(current) > version_key(latest):
        raise SystemExit(f"项目版本 {current} 高于当前框架 {latest}，已停止。")
    if current == latest:
        status(f"项目已是最新版本 {latest}。")
        sync_project_skills(project, args.dry_run)
        if not args.dry_run:
            write_state(project)
        return 0

    releases = releases_between(current, latest)
    status(f"检测到框架升级：{current} → {latest}")
    print_migration_plan(releases)
    if args.dry_run:
        sync_project_skills(project, dry_run=True)
        status("预览完成，未写入任何文件。")
        return 0
    if not args.yes:
        answer = input("输入 1 应用更新，其他任意输入取消：").strip()
        if answer != "1":
            status("已取消。")
            return 0

    merge_agents_section(project, dry_run=False)
    copy_template(project, "goals/GOAL-TEMPLATE.md", force=True, dry_run=False)
    sync_project_skills(project, dry_run=False)
    write_state(project)
    status(f"已更新到 {latest}。请根据上方“需要留意”项目决定是否手动调整项目文档。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
