#!/usr/bin/env python3
"""Initialize Goal Framework in a project for Codex, Cursor, or OpenCode."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = FRAMEWORK_ROOT / "templates"
START_MARKER = "<!-- GOAL-FRAMEWORK:START -->"
END_MARKER = "<!-- GOAL-FRAMEWORK:END -->"
NATIVE_PROMPT = (
    "分析当前项目，创建项目根目录的 AGENTS.md。内容应只包含从代码、配置和文档可验证的"
    "项目结构、开发命令和约定；不要虚构事实，不要覆盖用户已有文件。"
)


def status(message: str) -> None:
    print(f"[goal-init] {message}")


def warn(message: str) -> None:
    print(f"[goal-init] 警告：{message}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize Goal Framework in a project.")
    parser.add_argument("--project-path", "-p", default=".", help="Project directory (default: current directory).")
    parser.add_argument("--agent", choices=("auto", "codex", "cursor", "opencode", "manual"), default="auto")
    parser.add_argument("--skip-native-init", action="store_true", help="Do not create AGENTS.md through an agent.")
    parser.add_argument("--no-agent-prompt", action="store_true", help="Do not ask an agent to fill framework files.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing framework template files.")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without writing files or calling an agent.")
    return parser.parse_args()


def commands() -> dict[str, str | None]:
    return {
        "codex": shutil.which("codex"),
        "cursor": shutil.which("cursor-agent") or shutil.which("cursor"),
        "opencode": shutil.which("opencode"),
    }


def select_agent(requested: str, available: dict[str, str | None]) -> str:
    if requested != "auto":
        return requested
    return next((name for name in ("codex", "cursor", "opencode") if available[name]), "manual")


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


def run_agent(agent: str, command: str, prompt: str, cwd: Path) -> bool:
    if agent == "manual":
        return False
    if agent == "codex":
        args = [command, "exec", prompt]
    elif agent == "cursor":
        args = [command, "--print", prompt]
    elif agent == "opencode":
        args = [command, "run", prompt]
    else:
        raise ValueError(f"Unsupported agent: {agent}")
    try:
        subprocess.run(args, cwd=cwd, check=True)
        return True
    except (OSError, subprocess.CalledProcessError) as exc:
        warn(f"{agent} 调用未完成：{exc}")
        return False


def merge_agents_section(agents_path: Path, dry_run: bool) -> None:
    section = (TEMPLATES / "goal-framework-agents-section.md").read_text(encoding="utf-8").strip()
    block = f"{START_MARKER}\n{section}\n{END_MARKER}\n"
    if dry_run:
        status("将创建或更新 AGENTS.md 中的 Goal Framework 受管区块。")
        return
    current = agents_path.read_text(encoding="utf-8") if agents_path.exists() else "# 项目 Agent 说明\n"
    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
    if pattern.search(current):
        updated = pattern.sub(block.rstrip(), current).rstrip() + "\n"
        status("更新 AGENTS.md 中的 Goal Framework 受管区块。")
    else:
        updated = current.rstrip() + "\n\n" + block
        status("合并 Goal Framework 规则到 AGENTS.md。")
    agents_path.write_text(updated, encoding="utf-8")


def main() -> int:
    args = parse_args()
    project = Path(args.project_path).expanduser().resolve()
    if not project.is_dir():
        raise SystemExit(f"项目目录不存在：{project}")
    if not TEMPLATES.is_dir():
        raise SystemExit(f"找不到模板目录：{TEMPLATES}")

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
                # OpenCode supports /init; use an equivalent prompt when its command mode does not create AGENTS.md.
                run_agent(agent, command, "/init", project)
                if not agents_path.exists():
                    run_agent(agent, command, NATIVE_PROMPT, project)
            else:
                run_agent(agent, command, NATIVE_PROMPT, project)

    for relative_path in (
        "docs/PROJECT.md",
        "docs/CURRENT.md",
        "goals/GOAL-TEMPLATE.md",
        "GOAL-FRAMEWORK-PROMPT.md",
    ):
        copy_template(project, relative_path, args.force, args.dry_run)
    for relative_path in ("goals/active", "goals/archive"):
        status(f"确保目录：{relative_path}")
        if not args.dry_run:
            (project / relative_path).mkdir(parents=True, exist_ok=True)

    merge_agents_section(agents_path, args.dry_run)

    if not args.no_agent_prompt:
        if agent == "manual":
            status("未检测到可调用 Agent。请在你的 Agent 终端粘贴 GOAL-FRAMEWORK-PROMPT.md 的内容。")
        elif args.dry_run:
            status(f"将调用 {agent} 填写 PROJECT.md 和 CURRENT.md。")
        else:
            command = available[agent]
            if not command:
                warn(f"未找到 {agent} 命令。请在该 Agent 中打开并执行 GOAL-FRAMEWORK-PROMPT.md。")
            else:
                status(f"调用 {agent} 执行 Goal Framework 初始化提示。")
                prompt = (project / "GOAL-FRAMEWORK-PROMPT.md").read_text(encoding="utf-8")
                if not run_agent(agent, command, prompt, project):
                    warn(f"请在 {agent} 中打开并执行 GOAL-FRAMEWORK-PROMPT.md。")

    status("完成。请检查 AGENTS.md、docs/PROJECT.md 与 docs/CURRENT.md 后提交项目变更。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
