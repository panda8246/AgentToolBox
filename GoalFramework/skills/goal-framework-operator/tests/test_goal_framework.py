from __future__ import annotations

import contextlib
import importlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_ROOT / "scripts"
ENTRY_POINT = SCRIPT_DIR / "goal-framework"
sys.path.insert(0, str(SCRIPT_DIR))
core = importlib.import_module("goal_framework")
TODAY = core.model.today_iso()

CURRENT = """# 当前状态

- 最后更新：2026-01-01
- 当前阶段：实现

## 活跃目标

- 暂无。

## 待确认 / 阻塞

- 保留这个项目级提示。
"""

PROJECT = """# 项目总纲

## 项目愿景

可靠管理目标。
"""

AGENTS = f"""# 项目 Agent 说明

{core.model.START_MARKER}
# Goal Framework 项目规则
{core.model.END_MARKER}
"""


class GoalFrameworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "docs").mkdir()
        (self.root / "goals" / "active").mkdir(parents=True)
        (self.root / "goals" / "archive").mkdir()
        (self.root / ".goal-framework.json").write_text(
            json.dumps(
                {
                    "version": "1.1.0",
                    "initializedAt": "2026-01-01",
                    "updatedAt": "2026-01-01",
                }
            ),
            encoding="utf-8",
        )
        (self.root / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
        (self.root / "docs" / "PROJECT.md").write_text(PROJECT, encoding="utf-8")
        (self.root / "docs" / "CURRENT.md").write_text(CURRENT, encoding="utf-8")
        (self.root / "goals" / "GOAL-TEMPLATE.md").write_text(
            "# template\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_main(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = core.main(["--project", str(self.root), *arguments])
        return result, stdout.getvalue(), stderr.getvalue()

    def create_goal(
        self, slug: str = "export-data", goal_type: str = "delivery"
    ) -> Path:
        result, _, error = self.run_main(
            "new",
            "--title",
            "Export data",
            "--slug",
            slug,
            "--type",
            goal_type,
            "--purpose",
            "Allow verified exports.",
            "--condition",
            "Integration tests pass",
            "--condition",
            "Documentation is updated",
        )
        self.assertEqual(0, result, error)
        return self.root / "goals" / "active" / f"{TODAY}-{slug}.md"

    def create_plan(self, name: str, content: str = "free-form plan\n") -> Path:
        path = self.root / "docs" / "technical-plans" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_doctor_accepts_clean_initialized_project(self) -> None:
        result, output, error = self.run_main("doctor", "--strict")
        self.assertEqual(0, result, error)
        self.assertIn("检查通过", output)

    def test_full_lifecycle_updates_current_and_archives_with_evidence(self) -> None:
        active = self.create_goal()
        self.assertTrue(active.is_file())
        current = (self.root / "docs" / "CURRENT.md").read_text(encoding="utf-8")
        self.assertIn(active.name, current)
        self.assertIn("保留这个项目级提示", current)

        result, _, error = self.run_main(
            "checkpoint",
            active.name,
            "--done",
            "Implemented exporter",
            "--in-progress",
            "Writing documentation",
            "--blocked",
            "Waiting for fixture",
            "--next",
            "Add the fixture",
            "--satisfy",
            "1",
        )
        self.assertEqual(0, result, error)
        text = active.read_text(encoding="utf-8")
        self.assertIn("- 状态：阻塞", text)
        self.assertIn("- [x] Integration tests pass", text)
        self.assertIn("Implemented exporter", text)

        before_failed_complete = active.read_bytes()
        result, _, error = self.run_main(
            "complete", active.name, "--result", "Done", "--evidence", "tests passed"
        )
        self.assertEqual(2, result)
        self.assertIn("未满足", error)
        self.assertEqual(before_failed_complete, active.read_bytes())
        self.assertEqual([], list((self.root / "goals" / "archive").glob("*.md")))

        result, _, error = self.run_main(
            "checkpoint",
            active.name,
            "--done",
            "Updated documentation",
            "--clear-in-progress",
            "--clear-blocked",
            "--clear-next",
            "--satisfy",
            "2",
        )
        self.assertEqual(0, result, error)
        self.assertIn("- 状态：进行中", active.read_text(encoding="utf-8"))

        result, output, error = self.run_main(
            "complete",
            active.name,
            "--result",
            "Export support is ready.",
            "--evidence",
            "pytest: 42 passed",
            "--evidence",
            "CSV round-trip verified",
        )
        self.assertEqual(0, result, error)
        self.assertIn("已归档", output)
        self.assertFalse(active.exists())
        archive = self.root / "goals" / "archive" / active.name
        self.assertTrue(archive.is_file())
        archived_text = archive.read_text(encoding="utf-8")
        self.assertIn("- 状态：已完成", archived_text)
        self.assertIn(f"- 归档日期：{TODAY}", archived_text)
        self.assertIn("pytest: 42 passed", archived_text)
        current = (self.root / "docs" / "CURRENT.md").read_text(encoding="utf-8")
        self.assertNotIn(active.name, current)
        self.assertIn("保留这个项目级提示", current)
        result, output, _ = self.run_main("doctor", "--strict")
        self.assertEqual(0, result, output)

    def test_exploration_goal_uses_exploration_type(self) -> None:
        active = self.create_goal("choose-storage", "exploration")
        self.assertIn("- 类型：探索型", active.read_text(encoding="utf-8"))

    def test_new_goal_has_optional_plan_section_and_old_goal_can_attach(self) -> None:
        active = self.create_goal()
        text = active.read_text(encoding="utf-8")
        self.assertIn("## 技术方案\n\n暂无。", text)

        active.write_text(
            text.replace("\n## 技术方案\n\n暂无。\n", ""), encoding="utf-8"
        )
        result, _, error = self.run_main(
            "checkpoint", active.name, "--done", "Old goal remains writable"
        )
        self.assertEqual(0, result, error)

        document = self.create_plan("existing-goal.md")
        result, _, error = self.run_main(
            "plan", "attach", active.name, document.relative_to(self.root).as_posix()
        )
        self.assertEqual(0, result, error)
        text = active.read_text(encoding="utf-8")
        self.assertIn("## 技术方案", text)
        self.assertIn("[existing-goal.md]", text)

    def test_plan_attach_multiple_status_and_detach_missing_document(self) -> None:
        active = self.create_goal()
        first = self.create_plan("design one.md")
        second = self.create_plan("补充设计.md")
        for document in (first, second):
            result, _, error = self.run_main(
                "plan",
                "attach",
                active.name,
                document.relative_to(self.root).as_posix(),
            )
            self.assertEqual(0, result, error)

        text = active.read_text(encoding="utf-8")
        self.assertIn("[design one.md](../../docs/technical-plans/design%20one.md)", text)
        self.assertIn("[补充设计.md](../../docs/technical-plans/", text)
        result, output, error = self.run_main("status")
        self.assertEqual(0, result, error)
        self.assertIn("技术方案 2", output)

        first.unlink()
        result, output, _ = self.run_main("doctor")
        self.assertEqual(1, result)
        self.assertIn("plan.missing", output)
        result, _, error = self.run_main(
            "plan", "detach", active.name, first.relative_to(self.root).as_posix()
        )
        self.assertEqual(0, result, error)
        result, _, error = self.run_main(
            "plan", "detach", active.name, second.relative_to(self.root).as_posix()
        )
        self.assertEqual(0, result, error)
        self.assertTrue(second.is_file())
        self.assertIn(
            "## 技术方案\n\n暂无。", active.read_text(encoding="utf-8")
        )
        result, output, error = self.run_main("doctor", "--strict")
        self.assertEqual(0, result, error + output)

    def test_plan_attach_rejects_invalid_or_duplicate_documents(self) -> None:
        active = self.create_goal()
        plan = self.create_plan("valid.md")
        outside = self.root / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        non_markdown = self.create_plan("invalid.txt")
        original = active.read_bytes()
        original_current = (self.root / "docs" / "CURRENT.md").read_bytes()
        invalid = (
            ("docs/technical-plans/missing.md", "不存在"),
            (non_markdown.relative_to(self.root).as_posix(), "Markdown"),
            (outside.relative_to(self.root).as_posix(), "必须位于"),
            (str(plan.resolve()), "相对路径"),
            ("docs/technical-plans/../../outside.md", "必须位于"),
        )
        for document, message in invalid:
            result, _, error = self.run_main(
                "plan", "attach", active.name, document
            )
            self.assertEqual(2, result)
            self.assertIn(message, error)
            self.assertEqual(original, active.read_bytes())
            self.assertEqual(
                original_current, (self.root / "docs" / "CURRENT.md").read_bytes()
            )

        relative = plan.relative_to(self.root).as_posix()
        result, _, error = self.run_main("plan", "attach", active.name, relative)
        self.assertEqual(0, result, error)
        attached = active.read_bytes()
        current = (self.root / "docs" / "CURRENT.md").read_bytes()
        result, _, error = self.run_main("plan", "attach", active.name, relative)
        self.assertEqual(2, result)
        self.assertIn("已关联", error)
        self.assertEqual(attached, active.read_bytes())
        self.assertEqual(current, (self.root / "docs" / "CURRENT.md").read_bytes())

    def test_doctor_validates_malformed_outside_duplicate_and_archived_links(
        self,
    ) -> None:
        active = self.create_goal()
        plan = self.create_plan("archive-plan.md")
        relative = plan.relative_to(self.root).as_posix()
        result, _, error = self.run_main("plan", "attach", active.name, relative)
        self.assertEqual(0, result, error)

        valid = active.read_text(encoding="utf-8")
        link = "- [archive-plan.md](../../docs/technical-plans/archive-plan.md)"
        active.write_text(valid.replace(link, f"{link}\n{link}"), encoding="utf-8")
        result, output, _ = self.run_main("doctor")
        self.assertEqual(1, result)
        self.assertIn("plan.duplicate", output)

        active.write_text(
            valid.replace(
                link, "- [outside.md](../../outside.md)"
            ),
            encoding="utf-8",
        )
        result, output, _ = self.run_main("doctor")
        self.assertEqual(1, result)
        self.assertIn("plan.link", output)

        active.write_text(valid.replace(link, "- not-a-link"), encoding="utf-8")
        result, output, _ = self.run_main("doctor")
        self.assertEqual(1, result)
        self.assertIn("goal.parse", output)

        active.write_text(valid, encoding="utf-8")
        result, _, error = self.run_main(
            "checkpoint", active.name, "--satisfy", "1", "--satisfy", "2"
        )
        self.assertEqual(0, result, error)
        result, _, error = self.run_main(
            "complete", active.name, "--result", "Done", "--evidence", "Verified"
        )
        self.assertEqual(0, result, error)
        archive = self.root / "goals" / "archive" / active.name
        self.assertIn(link, archive.read_text(encoding="utf-8"))
        plan.unlink()
        result, output, _ = self.run_main("doctor")
        self.assertEqual(1, result)
        self.assertIn("plan.missing", output)

    def test_invalid_slug_and_duplicate_do_not_change_current(self) -> None:
        original = (self.root / "docs" / "CURRENT.md").read_bytes()
        result, _, error = self.run_main(
            "new",
            "--title",
            "Bad",
            "--slug",
            "Bad Slug",
            "--type",
            "delivery",
            "--purpose",
            "Bad slug test",
            "--condition",
            "Never written",
        )
        self.assertEqual(2, result)
        self.assertIn("slug", error)
        self.assertEqual(original, (self.root / "docs" / "CURRENT.md").read_bytes())
        self.assertFalse((self.root / core.model.LOCK_FILE).exists())

        self.create_goal()
        current = (self.root / "docs" / "CURRENT.md").read_bytes()
        result, _, _ = self.run_main(
            "new",
            "--title",
            "Duplicate",
            "--slug",
            "export-data",
            "--type",
            "delivery",
            "--purpose",
            "Duplicate test",
            "--condition",
            "Never written",
        )
        self.assertEqual(2, result)
        self.assertEqual(current, (self.root / "docs" / "CURRENT.md").read_bytes())

    def test_new_rejects_same_day_archived_slug(self) -> None:
        archive = self.root / "goals" / "archive" / f"{TODAY}-export-data.md"
        archive.write_text("existing archive", encoding="utf-8")
        original = (self.root / "docs" / "CURRENT.md").read_bytes()
        result, _, error = self.run_main(
            "new",
            "--title",
            "Duplicate archive",
            "--slug",
            "export-data",
            "--type",
            "delivery",
            "--purpose",
            "Prevent a later archive collision.",
            "--condition",
            "Creation is rejected",
        )
        self.assertEqual(2, result)
        self.assertIn("归档目标已存在", error)
        self.assertEqual(original, (self.root / "docs" / "CURRENT.md").read_bytes())

    def test_ambiguous_reference_is_rejected_without_changes(self) -> None:
        first = self.create_goal("export-csv")
        second = self.create_goal("export-json")
        snapshots = {first: first.read_bytes(), second: second.read_bytes()}
        result, _, error = self.run_main("checkpoint", "export", "--done", "Ambiguous")
        self.assertEqual(2, result)
        self.assertIn("不唯一", error)
        self.assertEqual(snapshots[first], first.read_bytes())
        self.assertEqual(snapshots[second], second.read_bytes())

        plan = self.create_plan("ambiguous.md")
        result, _, error = self.run_main(
            "plan", "attach", "export", plan.relative_to(self.root).as_posix()
        )
        self.assertEqual(2, result)
        self.assertIn("不唯一", error)
        self.assertEqual(snapshots[first], first.read_bytes())
        self.assertEqual(snapshots[second], second.read_bytes())

    def test_lock_blocks_mutation_and_strict_doctor_fails(self) -> None:
        lock = self.root / core.model.LOCK_FILE
        lock.write_text("pid=123\n", encoding="utf-8")
        result, _, error = self.run_main(
            "new",
            "--title",
            "Locked",
            "--slug",
            "locked",
            "--type",
            "delivery",
            "--purpose",
            "Exercise the lock.",
            "--condition",
            "No mutation occurs",
        )
        self.assertEqual(2, result)
        self.assertIn("写入锁", error)
        result, output, _ = self.run_main("doctor")
        self.assertEqual(0, result)
        self.assertIn("project.lock", output)
        result, _, _ = self.run_main("doctor", "--strict")
        self.assertEqual(1, result)

    def test_doctor_detects_current_drift_and_malformed_goal(self) -> None:
        active = self.create_goal()
        current_path = self.root / "docs" / "CURRENT.md"
        current_path.write_text(CURRENT, encoding="utf-8")
        result, output, _ = self.run_main("doctor")
        self.assertEqual(1, result)
        self.assertIn("current.links", output)

        text = active.read_text(encoding="utf-8").replace(
            "- [ ] Integration tests pass", "- Integration tests pass"
        )
        active.write_text(text, encoding="utf-8")
        result, output, _ = self.run_main("doctor")
        self.assertEqual(1, result)
        self.assertIn("goal.parse", output)

    def test_doctor_rejects_invalid_state_version(self) -> None:
        state_path = self.root / ".goal-framework.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["version"] = "latest"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result, output, _ = self.run_main("doctor")
        self.assertEqual(1, result)
        self.assertIn("state.version", output)

    def test_archive_collision_keeps_active_goal(self) -> None:
        active = self.create_goal()
        result, _, error = self.run_main(
            "checkpoint", active.name, "--satisfy", "1", "--satisfy", "2"
        )
        self.assertEqual(0, result, error)
        archive = self.root / "goals" / "archive" / active.name
        archive.write_text("collision", encoding="utf-8")
        snapshot = active.read_bytes()
        result, _, error = self.run_main(
            "complete", active.name, "--result", "Done", "--evidence", "Verified"
        )
        self.assertEqual(2, result)
        self.assertIn("已存在", error)
        self.assertEqual(snapshot, active.read_bytes())
        self.assertEqual(b"collision", archive.read_bytes())

    def test_transaction_rolls_back_when_second_write_fails(self) -> None:
        current_path = self.root / "docs" / "CURRENT.md"
        original_current = current_path.read_bytes()
        original_atomic_write = core.model.atomic_write
        calls = 0

        def fail_second_write(path: Path, content: str) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            original_atomic_write(path, content)

        arguments = [
            "--title",
            "Rollback",
            "--slug",
            "rollback",
            "--type",
            "delivery",
            "--purpose",
            "Verify rollback.",
            "--condition",
            "No partial state remains",
        ]
        with (
            mock.patch.object(
                core.model, "atomic_write", side_effect=fail_second_write
            ),
            self.assertRaises(OSError),
        ):
            parsed = core.build_parser().parse_args(
                ["--project", str(self.root), "new", *arguments]
            )
            core.dispatch(core.Project(self.root), parsed)
        target = self.root / "goals" / "active" / f"{TODAY}-rollback.md"
        self.assertFalse(target.exists())
        self.assertEqual(original_current, current_path.read_bytes())
        self.assertFalse((self.root / core.model.LOCK_FILE).exists())

    def test_plan_attach_rolls_back_when_current_write_fails(self) -> None:
        active = self.create_goal()
        plan = self.create_plan("rollback-plan.md")
        original_goal = active.read_bytes()
        current_path = self.root / "docs" / "CURRENT.md"
        original_current = current_path.read_bytes()
        original_atomic_write = core.model.atomic_write
        calls = 0

        def fail_second_write(path: Path, content: str) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated plan write failure")
            original_atomic_write(path, content)

        arguments = [
            "--project",
            str(self.root),
            "plan",
            "attach",
            active.name,
            plan.relative_to(self.root).as_posix(),
        ]
        with (
            mock.patch.object(
                core.model, "atomic_write", side_effect=fail_second_write
            ),
            self.assertRaises(OSError),
        ):
            parsed = core.build_parser().parse_args(arguments)
            core.dispatch(core.Project(self.root), parsed)
        self.assertEqual(original_goal, active.read_bytes())
        self.assertEqual(original_current, current_path.read_bytes())
        self.assertFalse((self.root / core.model.LOCK_FILE).exists())

    def test_real_entry_point_runs_in_subprocess(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ENTRY_POINT),
                "--project",
                str(self.root),
                "doctor",
                "--strict",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, completed.returncode, completed.stderr + completed.stdout)
        self.assertIn("检查通过", completed.stdout)


if __name__ == "__main__":
    unittest.main()
