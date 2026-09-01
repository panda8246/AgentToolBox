#!/usr/bin/env python3
"""Goal lifecycle commands and project consistency diagnostics."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote

from .model import (
    END_MARKER,
    FILENAME_RE,
    LINK_RE,
    LOCK_FILE,
    SLUG_RE,
    START_MARKER,
    STATE_FILE,
    TECHNICAL_PLANS_DIR,
    VALID_STATUSES,
    VALID_TYPES,
    FileTransaction,
    GoalDocument,
    GoalFrameworkError,
    Project,
    TechnicalPlanLink,
    condition_at,
    condition_leaves,
    conditions_from_arguments,
    parse_numbered_items,
    parse_subsection_bullets,
    read_text,
    render_checklist,
    render_goal,
    render_next,
    render_progress,
    refresh_condition_states,
    replace_metadata,
    replace_section,
    replace_technical_plan_links,
    section_body,
    today_iso,
    update_current,
    validate_date,
)


def status_command(project: Project) -> int:
    project.require_initialized()
    goals = project.active_goals()
    print(f"项目：{project.root}")
    if not goals:
        print("活跃目标：暂无")
        return 0
    print(f"活跃目标：{len(goals)}")
    for goal in goals:
        leaves = condition_leaves(goal.conditions)
        complete = sum(condition.checked for condition in leaves)
        print(
            f"- {goal.path.name} | {goal.status} | "
            f"完成条件 {complete}/{len(leaves)} | "
            f"技术方案 {len(goal.technical_plans)} | {goal.title}"
        )
    return 0


def normalize_plan_document(
    project: Project, value: str, *, require_exists: bool
) -> Path:
    if not value.strip():
        raise GoalFrameworkError("技术方案路径不能为空。")
    supplied = Path(value)
    if supplied.is_absolute():
        raise GoalFrameworkError("技术方案必须使用项目相对路径。")
    plan_root = (project.root / TECHNICAL_PLANS_DIR).resolve()
    resolved = (project.root / supplied).resolve()
    if not resolved.is_relative_to(plan_root):
        raise GoalFrameworkError(
            f"技术方案必须位于 {TECHNICAL_PLANS_DIR.as_posix()}/。"
        )
    if resolved.suffix.lower() != ".md":
        raise GoalFrameworkError("技术方案必须是 Markdown 文件（.md）。")
    if require_exists and not resolved.is_file():
        raise GoalFrameworkError(f"技术方案不存在：{value}")
    return resolved.relative_to(project.root)


def resolve_linked_plan(
    project: Project, goal_path: Path, link: TechnicalPlanLink
) -> Path:
    decoded = unquote(link.target)
    supplied = Path(decoded)
    if supplied.is_absolute():
        raise GoalFrameworkError("技术方案链接必须使用相对路径。")
    plan_root = (project.root / TECHNICAL_PLANS_DIR).resolve()
    resolved = (goal_path.parent / supplied).resolve()
    if not resolved.is_relative_to(plan_root):
        raise GoalFrameworkError(
            f"技术方案链接越出 {TECHNICAL_PLANS_DIR.as_posix()}/：{link.target}"
        )
    if resolved.suffix.lower() != ".md":
        raise GoalFrameworkError(f"技术方案链接不是 Markdown 文件：{link.target}")
    return resolved.relative_to(project.root)


def render_plan_target(goal_path: Path, document_path: Path, project: Project) -> str:
    relative = Path(
        os.path.relpath(project.root / document_path, start=goal_path.parent)
    ).as_posix()
    return quote(relative, safe="/-._~")


def escape_link_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def update_goal_plans(
    project: Project, goal: GoalDocument, links: list[TechnicalPlanLink]
) -> None:
    updated = today_iso()
    text = replace_technical_plan_links(goal.text, links)
    text = replace_metadata(text, "最近更新", updated)
    updated_goal = GoalDocument.from_text(goal.path, text)
    goals = [
        updated_goal if item.path == goal.path else item
        for item in project.active_goals()
    ]
    current_text = update_current(read_text(project.current_path), goals, updated)
    transaction = FileTransaction()
    transaction.write(goal.path, text)
    transaction.write(project.current_path, current_text)
    transaction.commit()


def plan_attach_command(project: Project, args: argparse.Namespace) -> int:
    project.require_initialized()
    goal = project.resolve_active(args.goal)
    document = normalize_plan_document(project, args.document, require_exists=True)
    linked_documents = [
        resolve_linked_plan(project, goal.path, link) for link in goal.technical_plans
    ]
    if document in linked_documents:
        raise GoalFrameworkError(f"目标已关联技术方案：{document.as_posix()}")
    link = TechnicalPlanLink(
        label=escape_link_label(document.name),
        target=render_plan_target(goal.path, document, project),
    )
    update_goal_plans(project, goal, [*goal.technical_plans, link])
    print(
        f"已关联：{goal.path.relative_to(project.root)} -> {document.as_posix()}"
    )
    return 0


def plan_detach_command(project: Project, args: argparse.Namespace) -> int:
    project.require_initialized()
    goal = project.resolve_active(args.goal)
    document = normalize_plan_document(project, args.document, require_exists=False)
    remaining = [
        link
        for link in goal.technical_plans
        if resolve_linked_plan(project, goal.path, link) != document
    ]
    if len(remaining) == len(goal.technical_plans):
        raise GoalFrameworkError(f"目标未关联技术方案：{document.as_posix()}")
    update_goal_plans(project, goal, remaining)
    print(
        f"已解除关联：{goal.path.relative_to(project.root)} -> {document.as_posix()}"
    )
    return 0


def new_command(project: Project, args: argparse.Namespace) -> int:
    project.require_initialized()
    if not SLUG_RE.fullmatch(args.slug):
        raise GoalFrameworkError(
            "slug 只能包含小写英文字母、数字和单连字符分隔的片段。"
        )
    if not args.title.strip() or not args.purpose.strip():
        raise GoalFrameworkError("title 和 purpose 不能为空。")
    conditions_from_arguments(args.condition)
    current_date = today_iso()
    target = project.active_dir / f"{current_date}-{args.slug}.md"
    if target.exists():
        raise GoalFrameworkError(f"活跃目标已存在：{target.name}")
    if (project.archive_dir / target.name).exists():
        raise GoalFrameworkError(f"同日同名归档目标已存在：{target.name}")
    goal_text = render_goal(
        title=args.title.strip(),
        goal_type=VALID_TYPES[args.type],
        purpose=args.purpose.strip(),
        conditions=args.condition,
        created=current_date,
    )
    new_goal = GoalDocument.from_text(target, goal_text)
    existing = project.active_goals()
    goals = sorted(existing + [new_goal], key=lambda goal: goal.path.name)
    current_text = update_current(read_text(project.current_path), goals, current_date)
    transaction = FileTransaction()
    transaction.write(target, goal_text)
    transaction.write(project.current_path, current_text)
    transaction.commit()
    print(f"已创建：{target.relative_to(project.root)}")
    return 0


def checkpoint_command(project: Project, args: argparse.Namespace) -> int:
    project.require_initialized()
    goal = project.resolve_active(args.goal)
    if goal.status == "已完成":
        raise GoalFrameworkError("已完成目标不能再写入检查点。")
    changed = any(
        (
            args.done,
            args.satisfy,
            args.in_progress is not None,
            args.blocked is not None,
            args.next is not None,
            args.clear_in_progress,
            args.clear_blocked,
            args.clear_next,
        )
    )
    if not changed:
        raise GoalFrameworkError("checkpoint 没有收到任何变更。")
    if args.in_progress is not None and args.clear_in_progress:
        raise GoalFrameworkError("不能同时设置和清空进行中事项。")
    if args.blocked is not None and args.clear_blocked:
        raise GoalFrameworkError("不能同时设置和清空阻塞事项。")
    if args.next is not None and args.clear_next:
        raise GoalFrameworkError("不能同时设置和清空下一步。")

    conditions = goal.conditions
    for index in args.satisfy:
        condition = condition_at(conditions, index)
        if not condition.is_leaf:
            raise GoalFrameworkError(
                f"父完成条件不能直接满足，请逐项验证其叶子条件：{index}"
            )
        condition.checked = True
    refresh_condition_states(conditions)

    progress = section_body(goal.text, "当前进度")
    done = parse_subsection_bullets(progress, "已完成")
    current = parse_subsection_bullets(progress, "进行中")
    blocked = parse_subsection_bullets(progress, "待确认 / 阻塞")
    done.extend(value.strip() for value in args.done if value.strip())
    if args.in_progress is not None:
        current = [value.strip() for value in args.in_progress if value.strip()]
    elif args.clear_in_progress:
        current = []
    if args.blocked is not None:
        blocked = [value.strip() for value in args.blocked if value.strip()]
    elif args.clear_blocked:
        blocked = []

    next_items = parse_numbered_items(section_body(goal.text, "下一步"))
    if args.next is not None:
        next_items = [value.strip() for value in args.next if value.strip()]
    elif args.clear_next:
        next_items = []

    updated = today_iso()
    status = "阻塞" if blocked else "进行中"
    text = replace_section(goal.text, "完成条件", render_checklist(conditions))
    text = replace_section(text, "当前进度", render_progress(done, current, blocked))
    text = replace_section(text, "下一步", render_next(next_items))
    text = replace_metadata(text, "状态", status)
    text = replace_metadata(text, "最近更新", updated)
    updated_goal = GoalDocument.from_text(goal.path, text)
    goals = [
        updated_goal if item.path == goal.path else item
        for item in project.active_goals()
    ]
    current_text = update_current(read_text(project.current_path), goals, updated)
    transaction = FileTransaction()
    transaction.write(goal.path, text)
    transaction.write(project.current_path, current_text)
    transaction.commit()
    print(f"已更新：{goal.path.relative_to(project.root)}")
    return 0


def complete_command(project: Project, args: argparse.Namespace) -> int:
    project.require_initialized()
    goal = project.resolve_active(args.goal)
    unchecked = [
        condition.text
        for condition in condition_leaves(goal.conditions)
        if not condition.checked
    ]
    if unchecked:
        raise GoalFrameworkError("仍有未满足的完成条件：" + "；".join(unchecked))
    evidence = [value.strip() for value in args.evidence if value.strip()]
    if not args.result.strip() or not evidence:
        raise GoalFrameworkError("complete 需要非空 result 和至少一条 evidence。")
    name_match = FILENAME_RE.fullmatch(goal.path.name)
    if not name_match:
        raise GoalFrameworkError(f"活跃目标命名无效：{goal.path.name}")
    archived = today_iso()
    archive_path = project.archive_dir / f"{archived}-{name_match.group(2)}.md"
    if archive_path.exists():
        raise GoalFrameworkError(f"归档目标已存在：{archive_path.name}")
    body = (
        args.result.strip()
        + "\n\n### 验证证据\n\n"
        + "\n".join(f"- {item}" for item in evidence)
    )
    text = replace_section(goal.text, "结果与归档", body)
    text = replace_metadata(text, "状态", "已完成")
    text = replace_metadata(text, "最近更新", archived)
    text = replace_metadata(text, "归档日期", archived, add=True)
    GoalDocument.from_text(archive_path, text)
    remaining = [item for item in project.active_goals() if item.path != goal.path]
    current_text = update_current(read_text(project.current_path), remaining, archived)
    transaction = FileTransaction()
    transaction.write(archive_path, text)
    transaction.write(project.current_path, current_text)
    transaction.delete(goal.path)
    transaction.commit()
    print(f"已归档：{archive_path.relative_to(project.root)}")
    return 0


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str


def inspect_goal(path: Path, *, archived: bool) -> list[Finding]:
    findings: list[Finding] = []
    filename = FILENAME_RE.fullmatch(path.name)
    if not filename:
        findings.append(Finding("ERROR", "goal.filename", f"命名无效：{path}"))
    try:
        goal = GoalDocument.load(path)
    except GoalFrameworkError as exc:
        return findings + [Finding("ERROR", "goal.parse", f"{path}: {exc}")]
    if goal.goal_type not in VALID_TYPES.values():
        findings.append(
            Finding("ERROR", "goal.type", f"{path.name}: 未知类型 {goal.goal_type}")
        )
    if goal.status not in VALID_STATUSES:
        findings.append(
            Finding("ERROR", "goal.status", f"{path.name}: 未知状态 {goal.status}")
        )
    for label, value in (("创建日期", goal.created), ("最近更新", goal.updated)):
        try:
            validate_date(value, label)
        except GoalFrameworkError as exc:
            findings.append(Finding("ERROR", "goal.date", f"{path.name}: {exc}"))
    if archived:
        if goal.status != "已完成":
            findings.append(
                Finding(
                    "ERROR", "archive.status", f"{path.name}: 归档目标状态不是已完成"
                )
            )
        if not goal.archived:
            findings.append(
                Finding("WARN", "archive.date", f"{path.name}: 缺少归档日期")
            )
        else:
            try:
                validate_date(goal.archived, "归档日期")
            except GoalFrameworkError as exc:
                findings.append(Finding("ERROR", "archive.date", f"{path.name}: {exc}"))
            if filename and goal.archived != filename.group(1):
                findings.append(
                    Finding(
                        "ERROR",
                        "archive.filename-date",
                        f"{path.name}: 文件日期与归档日期不一致",
                    )
                )
    else:
        if goal.status == "已完成":
            findings.append(
                Finding(
                    "ERROR", "active.completed", f"{path.name}: 已完成目标仍在 active"
                )
            )
        if filename and goal.created != filename.group(1):
            findings.append(
                Finding(
                    "ERROR",
                    "active.filename-date",
                    f"{path.name}: 文件日期与创建日期不一致",
                )
            )
    return findings


def inspect_technical_plans(project: Project, goal: GoalDocument) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[Path] = set()
    for link in goal.technical_plans:
        try:
            document = resolve_linked_plan(project, goal.path, link)
        except GoalFrameworkError as exc:
            findings.append(
                Finding("ERROR", "plan.link", f"{goal.path.name}: {exc}")
            )
            continue
        if document in seen:
            findings.append(
                Finding(
                    "ERROR",
                    "plan.duplicate",
                    f"{goal.path.name}: 重复关联 {document.as_posix()}",
                )
            )
            continue
        seen.add(document)
        if not (project.root / document).is_file():
            findings.append(
                Finding(
                    "ERROR",
                    "plan.missing",
                    f"{goal.path.name}: 技术方案不存在 {document.as_posix()}",
                )
            )
    return findings


def doctor_findings(project: Project) -> list[Finding]:
    findings: list[Finding] = []
    required = (
        project.root / STATE_FILE,
        project.root / "AGENTS.md",
        project.root / "docs" / "PROJECT.md",
        project.current_path,
        project.root / "goals" / "GOAL-TEMPLATE.md",
        project.active_dir,
        project.archive_dir,
    )
    for path in required:
        if not path.exists():
            findings.append(Finding("ERROR", "project.missing", f"缺少：{path}"))
    state_path = project.root / STATE_FILE
    if state_path.is_file():
        try:
            state = json.loads(read_text(state_path))
            version = state.get("version")
            if not isinstance(version, str) or not re.fullmatch(
                r"\d+\.\d+\.\d+", version
            ):
                findings.append(
                    Finding("ERROR", "state.version", f"{STATE_FILE} 缺少有效 version")
                )
        except (json.JSONDecodeError, GoalFrameworkError) as exc:
            findings.append(Finding("ERROR", "state.json", f"{STATE_FILE} 无效：{exc}"))
    agents = project.root / "AGENTS.md"
    if agents.is_file():
        text = read_text(agents)
        if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
            findings.append(
                Finding("ERROR", "agents.markers", "AGENTS.md 的受管标记必须各出现一次")
            )
        elif text.index(START_MARKER) > text.index(END_MARKER):
            findings.append(
                Finding("ERROR", "agents.marker-order", "AGENTS.md 的受管标记顺序错误")
            )
    if (project.root / LOCK_FILE).exists():
        findings.append(
            Finding("WARN", "project.lock", f"存在写入锁：{project.root / LOCK_FILE}")
        )
    if project.active_dir.is_dir():
        for path in sorted(project.active_dir.glob("*.md")):
            findings.extend(inspect_goal(path, archived=False))
            try:
                findings.extend(
                    inspect_technical_plans(project, GoalDocument.load(path))
                )
            except GoalFrameworkError:
                pass
    if project.archive_dir.is_dir():
        for path in sorted(project.archive_dir.glob("*.md")):
            findings.extend(inspect_goal(path, archived=True))
            try:
                findings.extend(
                    inspect_technical_plans(project, GoalDocument.load(path))
                )
            except GoalFrameworkError:
                pass
    if project.current_path.is_file() and project.active_dir.is_dir():
        try:
            current = read_text(project.current_path)
            body = section_body(current, "活跃目标")
            linked = set(LINK_RE.findall(body))
            actual = {path.name for path in project.active_dir.glob("*.md")}
            if linked != actual:
                details: list[str] = []
                if missing := sorted(actual - linked):
                    details.append("未链接=" + ",".join(missing))
                if stale := sorted(linked - actual):
                    details.append("失效链接=" + ",".join(stale))
                findings.append(
                    Finding(
                        "ERROR",
                        "current.links",
                        "CURRENT.md 与 active 不一致：" + "；".join(details),
                    )
                )
        except GoalFrameworkError as exc:
            findings.append(Finding("ERROR", "current.parse", str(exc)))
    return findings


def doctor_command(project: Project, strict: bool) -> int:
    if not project.root.is_dir():
        raise GoalFrameworkError(f"项目目录不存在：{project.root}")
    findings = doctor_findings(project)
    if not findings:
        print("Goal Framework 检查通过。")
        return 0
    for finding in findings:
        print(f"[{finding.severity}] {finding.code}: {finding.message}")
    errors = sum(item.severity == "ERROR" for item in findings)
    warnings = sum(item.severity == "WARN" for item in findings)
    print(f"检查完成：{errors} 个错误，{warnings} 个警告。")
    return 1 if errors or (strict and warnings) else 0
