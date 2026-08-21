#!/usr/bin/env python3
"""Argument parsing and dispatch for the goal-framework command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .commands import (
    checkpoint_command,
    complete_command,
    doctor_command,
    new_command,
    plan_attach_command,
    plan_detach_command,
    status_command,
)
from .model import VALID_TYPES, GoalFrameworkError, Project, ProjectLock


def add_checkpoint_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("goal", help="Active goal filename or unique stem fragment")
    parser.add_argument(
        "--done", action="append", default=[], help="Append a completed fact"
    )
    parser.add_argument(
        "--in-progress", action="append", help="Replace current work items"
    )
    parser.add_argument("--blocked", action="append", help="Replace blocked items")
    parser.add_argument("--next", action="append", help="Replace next steps")
    parser.add_argument(
        "--satisfy",
        action="append",
        type=int,
        default=[],
        help="Mark condition index satisfied",
    )
    parser.add_argument("--clear-in-progress", action="store_true")
    parser.add_argument("--clear-blocked", action="store_true")
    parser.add_argument("--clear-next", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goal-framework", description="Operate a Goal Framework project."
    )
    parser.add_argument(
        "--project", "-p", default=".", help="Project root (default: current directory)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Show active goal status")
    doctor = subparsers.add_parser(
        "doctor", help="Validate framework structure and consistency"
    )
    doctor.add_argument(
        "--strict", action="store_true", help="Treat warnings as a failing result"
    )
    create = subparsers.add_parser("new", help="Create and register an active goal")
    create.add_argument("--title", required=True)
    create.add_argument("--slug", required=True)
    create.add_argument("--type", choices=tuple(VALID_TYPES), required=True)
    create.add_argument("--purpose", required=True)
    create.add_argument("--condition", action="append", required=True)
    checkpoint = subparsers.add_parser(
        "checkpoint", help="Record progress and satisfy conditions"
    )
    add_checkpoint_arguments(checkpoint)
    complete = subparsers.add_parser("complete", help="Archive a fully satisfied goal")
    complete.add_argument("goal")
    complete.add_argument("--result", required=True)
    complete.add_argument("--evidence", action="append", required=True)
    plan = subparsers.add_parser("plan", help="Manage technical plan links")
    plan_subparsers = plan.add_subparsers(dest="plan_command", required=True)
    attach = plan_subparsers.add_parser(
        "attach", help="Attach an existing technical plan to an active goal"
    )
    attach.add_argument("goal")
    attach.add_argument("document")
    detach = plan_subparsers.add_parser(
        "detach", help="Detach a technical plan without deleting it"
    )
    detach.add_argument("goal")
    detach.add_argument("document")
    return parser


def dispatch(project: Project, args: argparse.Namespace) -> int:
    if args.command == "status":
        return status_command(project)
    if args.command == "doctor":
        return doctor_command(project, args.strict)
    project.require_initialized()
    with ProjectLock(project.root):
        if args.command == "new":
            return new_command(project, args)
        if args.command == "checkpoint":
            return checkpoint_command(project, args)
        if args.command == "complete":
            return complete_command(project, args)
        if args.command == "plan":
            if args.plan_command == "attach":
                return plan_attach_command(project, args)
            if args.plan_command == "detach":
                return plan_detach_command(project, args)
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return dispatch(Project(Path(args.project)), args)
    except (GoalFrameworkError, OSError) as exc:
        print(f"goal-framework: 错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
