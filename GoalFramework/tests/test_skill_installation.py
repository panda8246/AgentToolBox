from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
INIT_COMMAND = FRAMEWORK_ROOT / "bin" / "goal-init.py"
UPDATE_COMMAND = FRAMEWORK_ROOT / "bin" / "goal-update.py"
SOURCE_SKILL = FRAMEWORK_ROOT / "skills" / "goal-framework-operator"
INSTALLED_SKILL = Path(".agents") / "skills" / "goal-framework-operator"
FRAMEWORK_VERSION = (FRAMEWORK_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def source_runtime_files() -> set[str]:
    files: set[str] = set()
    for path in SOURCE_SKILL.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(SOURCE_SKILL)
        if (
            "tests" in relative.parts
            or "__pycache__" in relative.parts
            or path.suffix.lower() in {".pyc", ".pyo"}
            or path.name.endswith("$py.class")
        ):
            continue
        files.add(relative.as_posix())
    return files


class SkillInstallationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_python(
        self, script: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def initialize(self) -> subprocess.CompletedProcess[str]:
        result = self.run_python(
            INIT_COMMAND,
            "--project-path",
            str(self.project),
            "--agent",
            "manual",
            "--skip-native-init",
            "--no-agent-prompt",
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        return result

    def installed_files(self) -> set[str]:
        root = self.project / INSTALLED_SKILL
        return {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }

    def test_init_installs_only_runtime_skill_files_and_records_them(self) -> None:
        result = self.initialize()
        self.assertIn("安装项目 skill", result.stdout)
        self.assertEqual(source_runtime_files(), self.installed_files())
        self.assertNotIn("tests/test_goal_framework.py", self.installed_files())
        self.assertFalse(
            any(path.endswith((".pyc", ".pyo")) for path in self.installed_files())
        )

        state = json.loads(
            (self.project / ".goal-framework.json").read_text(encoding="utf-8")
        )
        installed_state = state["skills"]["goal-framework-operator"]
        self.assertEqual(FRAMEWORK_VERSION, installed_state["version"])
        self.assertEqual(source_runtime_files(), set(installed_state["files"]))

        installed_command = (
            self.project / INSTALLED_SKILL / "scripts" / "goal-framework"
        )
        doctor = self.run_python(
            installed_command, "--project", str(self.project), "doctor", "--strict"
        )
        self.assertEqual(0, doctor.returncode, doctor.stderr + doctor.stdout)
        self.assertIn("检查通过", doctor.stdout)
        self.assertFalse((self.project / "docs" / "technical-plans").exists())
        agents = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## 技术方案留档", agents)
        self.assertIn("docs/technical-plans/<name>.md", agents)
        self.assertIn("普通的方案讨论、评审或头脑风暴不代表用户授权写文件", agents)

        gitignore_rules = (self.project / ".gitignore").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertIn("__pycache__/", gitignore_rules)
        self.assertIn("*.pyc", gitignore_rules)
        self.assertIn("*.pyo", gitignore_rules)

    def test_init_merges_missing_bytecode_rules_into_existing_gitignore(self) -> None:
        gitignore_path = self.project / ".gitignore"
        gitignore_path.write_text("node_modules/\n*.pyc\n", encoding="utf-8")

        self.initialize()
        updated = gitignore_path.read_text(encoding="utf-8")
        self.assertIn("node_modules/\n", updated)
        self.assertEqual(1, updated.splitlines().count("*.pyc"))
        self.assertIn("__pycache__/", updated.splitlines())
        self.assertIn("*.pyo", updated.splitlines())

        self.initialize()
        self.assertEqual(updated, gitignore_path.read_text(encoding="utf-8"))

    def test_init_dry_run_does_not_create_project_files(self) -> None:
        result = self.run_python(
            INIT_COMMAND,
            "--project-path",
            str(self.project),
            "--agent",
            "manual",
            "--skip-native-init",
            "--no-agent-prompt",
            "--dry-run",
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("安装项目 skill", result.stdout)
        self.assertEqual([], list(self.project.iterdir()))

    def test_latest_update_repairs_managed_files_and_preserves_custom_files(
        self,
    ) -> None:
        self.initialize()
        target = self.project / INSTALLED_SKILL
        managed = target / "SKILL.md"
        managed.write_text("modified\n", encoding="utf-8")
        custom = target / "notes.local.md"
        custom.write_text("keep me\n", encoding="utf-8")
        stale = target / "scripts" / "legacy.py"
        stale.write_text("old\n", encoding="utf-8")
        cache = target / "scripts" / "__pycache__" / "local.cpython-312.pyc"
        cache.parent.mkdir()
        cache.write_bytes(b"user cache")

        state_path = self.project / ".goal-framework.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["skills"]["goal-framework-operator"]["files"].append("scripts/legacy.py")
        state["skills"]["goal-framework-operator"]["files"].append(
            "scripts/__pycache__/local.cpython-312.pyc"
        )
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        result = self.run_python(
            UPDATE_COMMAND, "--project-path", str(self.project), "--yes"
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("项目已是最新版本", result.stdout)
        self.assertEqual((SOURCE_SKILL / "SKILL.md").read_bytes(), managed.read_bytes())
        self.assertEqual("keep me\n", custom.read_text(encoding="utf-8"))
        self.assertFalse(stale.exists())
        self.assertEqual(b"user cache", cache.read_bytes())

        state = json.loads(state_path.read_text(encoding="utf-8"))
        files = set(state["skills"]["goal-framework-operator"]["files"])
        self.assertEqual(source_runtime_files(), files)
        self.assertFalse(any(path.endswith((".pyc", ".pyo")) for path in files))

    def test_update_adds_bytecode_rules_for_existing_project(self) -> None:
        self.initialize()
        gitignore_path = self.project / ".gitignore"
        gitignore_path.unlink()

        state_path = self.project / ".goal-framework.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["version"] = "1.4.1"
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        result = self.run_python(
            UPDATE_COMMAND, "--project-path", str(self.project), "--yes"
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("1.4.1 → 1.4.2", result.stdout)
        self.assertIn("__pycache__/", gitignore_path.read_text(encoding="utf-8"))

    def test_repository_gitignore_covers_python_bytecode(self) -> None:
        rules = (
            (FRAMEWORK_ROOT.parent / ".gitignore")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        self.assertIn("__pycache__/", rules)
        self.assertIn("*.pyc", rules)
        self.assertIn("*.pyo", rules)

    def test_update_from_1_2_installs_skill_without_touching_project_state_docs(
        self,
    ) -> None:
        self.initialize()
        target = self.project / INSTALLED_SKILL
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        target.rmdir()

        state_path = self.project / ".goal-framework.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["version"] = "1.2.0"
        state.pop("skills")
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        current_path = self.project / "docs" / "CURRENT.md"
        current = (
            current_path.read_text(encoding="utf-8") + "\n<!-- keep-project-state -->\n"
        )
        current_path.write_text(current, encoding="utf-8")
        plan_path = self.project / "docs" / "technical-plans" / "preserved.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("user-owned technical plan\n", encoding="utf-8")
        active_path = self.project / "goals" / "active" / "2026-01-01-existing.md"
        active_path.write_text("user-owned goal\n", encoding="utf-8")

        result = self.run_python(
            UPDATE_COMMAND, "--project-path", str(self.project), "--yes"
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn(f"1.2.0 → {FRAMEWORK_VERSION}", result.stdout)
        self.assertEqual(source_runtime_files(), self.installed_files())
        self.assertIn("keep-project-state", current_path.read_text(encoding="utf-8"))
        self.assertEqual(
            "user-owned technical plan\n", plan_path.read_text(encoding="utf-8")
        )
        self.assertEqual("user-owned goal\n", active_path.read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(FRAMEWORK_VERSION, state["version"])

    def test_update_from_1_4_0_installs_persistence_prompt_without_touching_docs(
        self,
    ) -> None:
        self.initialize()
        state_path = self.project / ".goal-framework.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["version"] = "1.4.0"
        state["skills"]["goal-framework-operator"]["version"] = "1.4.0"
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        agents_path = self.project / "AGENTS.md"
        agents_path.write_text(
            """# 项目 Agent 说明

<!-- GOAL-FRAMEWORK:START -->
# Goal Framework 1.4.0 rules

- 技术方案仅在用户明确要求留档时创建。
<!-- GOAL-FRAMEWORK:END -->
""",
            encoding="utf-8",
        )
        plan_path = self.project / "docs" / "technical-plans" / "preserved.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("keep this plan unchanged\n", encoding="utf-8")
        current_path = self.project / "docs" / "CURRENT.md"
        current_before = current_path.read_bytes()

        result = self.run_python(
            UPDATE_COMMAND, "--project-path", str(self.project), "--yes"
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn(f"1.4.0 → {FRAMEWORK_VERSION}", result.stdout)

        agents = agents_path.read_text(encoding="utf-8")
        self.assertIn("## 技术方案留档", agents)
        self.assertIn("docs/technical-plans/<name>.md", agents)
        self.assertIn("运行 `goal-framework doctor`", agents)
        installed_skill = (
            self.project / INSTALLED_SKILL / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("## Technical plan persistence", installed_skill)
        self.assertEqual(
            "keep this plan unchanged\n", plan_path.read_text(encoding="utf-8")
        )
        self.assertEqual(current_before, current_path.read_bytes())
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(FRAMEWORK_VERSION, state["version"])


if __name__ == "__main__":
    unittest.main()
