#!/usr/bin/env python3
"""Initialize Goal Framework in a project for Codex, Cursor, or OpenCode."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from goal_framework import TEMPLATES, commands, copy_template, merge_agents_section, status, warn, write_state

NATIVE_PROMPT = (
    "分析当前项目，创建项目根目录的 AGENTS.md。内容应只包含从代码、配置和文档可验证的"
    "项目结构、开发命令和约定；不要虚构事实，不要覆盖用户已有文件。"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize Goal Framework in a project.")
    parser.add_argument("--project-path", "-p", default=".")
    parser.add_argument("--agent", choices=("auto", "codex", "cursor", "opencode", "manual"), default="auto")
    parser.add_argument("--skip-native-init", action="store_true")
    parser.add_argument("--no-agent-prompt", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def select_agent(requested: str, available: dict[str, str | None]) -> str:
    if requested != "auto":
        return requested
    return next((name for name in ("opencode", "codex", "cursor") if available[name]), "manual")


def run_agent(agent: str, command: str, prompt: str, cwd: Path) -> bool:
    args = {"codex": [command, "exec", prompt], "cursor": [command, "--print", prompt], "opencode": [command, "run", prompt]}[agent]
    try:
        subprocess.run(args, cwd=cwd, check=True)
        return True
    except (OSError, subprocess.CalledProcessError) as exc:
        warn(f"{agent} 调用未完成：{exc}")
        return False


def main() -> int:
    args = parse_args()
    project = Path(args.project_path).expanduser().resolve()
    if not project.is_dir():
        raise SystemExit(f"项目目录不存在：{project}")
    available = commands()
    agent = select_agent(args.agent, available)
    status(f"项目：{project}；Agent：{agent}")
    agents_path = project / "AGENTS.md"

    if not agents_path.exists() and not args.skip_native_init and agent != "manual":
        status(f"未发现 AGENTS.md，运行 {agent} 的项目上下文初始化。")
        if not args.dry_run:
            command = available[agent]
            if not command:
                warn(f"未找到 {agent} 命令。将继续创建 Goal Framework；请稍后手动执行该终端的 /init。")
            elif agent == "opencode":
                run_agent(agent, command, "/init", project)
                if not agents_path.exists():
                    run_agent(agent, command, NATIVE_PROMPT, project)
            else:
                run_agent(agent, command, NATIVE_PROMPT, project)

    for relative_path in ("docs/PROJECT.md", "docs/CURRENT.md", "goals/GOAL-TEMPLATE.md"):
        copy_template(project, relative_path, args.force, args.dry_run)
    for relative_path in ("goals/active", "goals/archive"):
        status(f"确保目录：{relative_path}")
        if not args.dry_run:
            (project / relative_path).mkdir(parents=True, exist_ok=True)
    merge_agents_section(project, args.dry_run)
    write_state(project, dry_run=args.dry_run)

    if not args.no_agent_prompt:
        if agent == "manual":
            status("未检测到可调用 Agent。请将 templates/goal-framework-init-prompt.md 的内容粘贴到你的 Agent 终端。")
        elif args.dry_run:
            status(f"将调用 {agent} 填写 PROJECT.md 和 CURRENT.md。")
        else:
            command = available[agent]
            prompt = (TEMPLATES / "goal-framework-init-prompt.md").read_text(encoding="utf-8")
            if command and not run_agent(agent, command, prompt, project):
                warn("请在所选 Agent 中手动执行 templates/goal-framework-init-prompt.md 的内容。")

    status("完成。请检查 AGENTS.md、docs/PROJECT.md 与 docs/CURRENT.md 后提交项目变更。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
