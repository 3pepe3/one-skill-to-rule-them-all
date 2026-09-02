#!/usr/bin/env python3
"""Integration tests for the dependency-free Codex installer."""

from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "install.py"
VALIDATOR = REPO_ROOT / "skill" / "task-observer" / "scripts" / "validate.py"


def run_installer(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER), "--codex-home", str(home), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def tree_snapshot(root: Path) -> dict[str, tuple[str, bytes]]:
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[str, bytes]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[relative] = ("dir", b"")
        elif path.is_file():
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


def observer_handler_count(hooks: dict) -> int:
    count = 0
    for groups in hooks.get("hooks", {}).values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for handler in group.get("hooks", []):
                if (
                    isinstance(handler, dict)
                    and "task-observer/scripts/task_observer.py"
                    in str(handler.get("command", ""))
                ):
                    count += 1
    return count


def load_installer_module():
    spec = importlib.util.spec_from_file_location("task_observer_installer", INSTALLER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load installer module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "codex-home"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_clean_install_preserves_unrelated_hooks_and_config(self) -> None:
        self.home.mkdir(parents=True)
        existing_hooks = {
            "description": "Synthetic existing hooks",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "/usr/bin/check-command",
                                "timeout": 7,
                            }
                        ],
                    }
                ]
            },
        }
        (self.home / "hooks.json").write_text(
            json.dumps(existing_hooks, indent=2) + "\n", encoding="utf-8"
        )
        original_config = (
            '# synthetic configuration\n'
            'model = "example-model"\n\n'
            '[features]\n'
            'multi_agent = false\n'
            'hooks = false # keep this explanation\n\n'
            '[mcp_servers.example]\n'
            'command = "example-server"\n'
        )
        (self.home / "config.toml").write_text(original_config, encoding="utf-8")

        result = run_installer(self.home)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("/hooks", result.stdout)
        self.assertTrue((self.home / "skills/task-observer/SKILL.md").is_file())
        self.assertTrue(
            (self.home / "task-observer/observation-log/archive").is_dir()
        )
        installed_hooks = json.loads((self.home / "hooks.json").read_text())
        self.assertEqual(
            installed_hooks["hooks"]["PreToolUse"],
            existing_hooks["hooks"]["PreToolUse"],
        )
        self.assertIn("SessionStart", installed_hooks["hooks"])
        self.assertIn("SubagentStart", installed_hooks["hooks"])
        self.assertEqual(observer_handler_count(installed_hooks), 2)
        config_text = (self.home / "config.toml").read_text(encoding="utf-8")
        parsed = tomllib.loads(config_text)
        self.assertTrue(parsed["features"]["hooks"])
        self.assertFalse(parsed["features"]["multi_agent"])
        self.assertEqual(parsed["model"], "example-model")
        self.assertEqual(parsed["mcp_servers"]["example"]["command"], "example-server")
        self.assertIn("hooks = true # keep this explanation", config_text)
        self.assertIn("# synthetic configuration", config_text)

        validation = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                str(self.home / "skills/task-observer"),
                "--hooks-json",
                str(self.home / "hooks.json"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)

    def test_reinstall_is_idempotent_without_duplicate_hooks_or_new_backups(self) -> None:
        first = run_installer(self.home)
        self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
        before = tree_snapshot(self.home)

        second = run_installer(self.home)

        self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
        self.assertEqual(tree_snapshot(self.home), before)
        installed_hooks = json.loads((self.home / "hooks.json").read_text())
        self.assertEqual(observer_handler_count(installed_hooks), 2)

    def test_merge_preserves_empty_and_mixed_unrelated_hook_groups(self) -> None:
        self.home.mkdir(parents=True)
        existing = {
            "hooks": {
                "SessionStart": [
                    {"matcher": "resume", "hooks": []},
                    {
                        "matcher": "startup",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 /old/task-observer/scripts/task_observer.py session-start",
                            },
                            {"type": "command", "command": "/usr/bin/keep-session-hook"},
                        ],
                    },
                ]
            }
        }
        (self.home / "hooks.json").write_text(
            json.dumps(existing) + "\n", encoding="utf-8"
        )

        result = run_installer(self.home)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        groups = json.loads((self.home / "hooks.json").read_text())["hooks"][
            "SessionStart"
        ]
        self.assertIn({"matcher": "resume", "hooks": []}, groups)
        self.assertIn(
            {
                "matcher": "startup",
                "hooks": [{"type": "command", "command": "/usr/bin/keep-session-hook"}],
            },
            groups,
        )
        self.assertEqual(
            observer_handler_count(json.loads((self.home / "hooks.json").read_text())),
            2,
        )

    def test_existing_skill_and_configuration_are_backed_up_before_update(self) -> None:
        old_skill = self.home / "skills" / "task-observer"
        old_skill.mkdir(parents=True)
        (old_skill / "old.txt").write_text("old skill bytes\n", encoding="utf-8")
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
        (self.home / "config.toml").write_text('model = "synthetic"\n', encoding="utf-8")

        result = run_installer(self.home)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        backup_roots = list((self.home / "backups" / "task-observer").iterdir())
        self.assertEqual(len(backup_roots), 1)
        backup = backup_roots[0]
        self.assertEqual(
            (backup / "skills/task-observer/old.txt").read_text(encoding="utf-8"),
            "old skill bytes\n",
        )
        self.assertEqual(
            (backup / "config.toml").read_text(encoding="utf-8"),
            'model = "synthetic"\n',
        )
        self.assertEqual(
            (backup / "hooks.json").read_text(encoding="utf-8"),
            '{"hooks": {}}\n',
        )
        self.assertFalse((old_skill / "old.txt").exists())

    def test_malformed_existing_files_fail_before_any_mutation(self) -> None:
        for relative, malformed in (
            ("hooks.json", "{not-json\n"),
            ("config.toml", "[features\nhooks = true\n"),
        ):
            with self.subTest(relative=relative):
                case_home = Path(self.temp.name) / relative.replace(".", "-")
                case_home.mkdir(parents=True)
                (case_home / relative).write_text(malformed, encoding="utf-8")
                before = tree_snapshot(case_home)

                result = run_installer(case_home)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(relative, result.stderr)
                self.assertIn("invalid", result.stderr.lower())
                self.assertEqual(tree_snapshot(case_home), before)

    def test_check_mode_validates_without_creating_the_codex_home(self) -> None:
        result = run_installer(self.home, "--check")

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("check passed", result.stdout.lower())
        self.assertFalse(self.home.exists())

    def test_custom_codex_home_is_the_only_root_in_generated_hook_commands(self) -> None:
        result = run_installer(self.home)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        hooks = json.loads((self.home / "hooks.json").read_text())
        commands = []
        for groups in hooks["hooks"].values():
            for group in groups:
                for handler in group.get("hooks", []):
                    command = str(handler.get("command", ""))
                    if "task-observer" in command:
                        commands.append(command)

        self.assertEqual(len(commands), 2)
        resolved_home = str(self.home.resolve())
        for command in commands:
            self.assertIn(resolved_home, command)
            self.assertNotIn(str(REPO_ROOT), command)
            self.assertTrue(command.endswith("session-start"))

    def test_plan_mode_hook_does_not_initialize_state(self) -> None:
        installed = run_installer(self.home)
        self.assertEqual(installed.returncode, 0, installed.stderr or installed.stdout)
        state = self.home / "task-observer"
        for path in sorted(state.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        state.rmdir()
        helper = self.home / "skills/task-observer/scripts/task_observer.py"
        event = {
            "hook_event_name": "SessionStart",
            "source": "startup",
            "permission_mode": "plan",
            "cwd": "/synthetic/project",
            "session_id": "synthetic-session",
        }

        result = subprocess.run(
            [sys.executable, str(helper), "--state-root", str(state), "session-start"],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("initialization=deferred", result.stdout)
        self.assertNotIn("synthetic-session", result.stdout)
        self.assertNotIn("/synthetic/project", result.stdout)
        self.assertFalse(state.exists())

    def test_write_failure_rolls_back_every_target(self) -> None:
        old_skill = self.home / "skills" / "task-observer"
        old_skill.mkdir(parents=True)
        (old_skill / "old.txt").write_text("old skill\n", encoding="utf-8")
        (self.home / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
        (self.home / "config.toml").write_text('model = "synthetic"\n', encoding="utf-8")
        before = tree_snapshot(self.home)
        installer = load_installer_module()
        real_replace = os.replace

        def fail_config_commit(source, destination):
            source_path = Path(source)
            destination_path = Path(destination)
            if (
                destination_path == self.home / "config.toml"
                and "rollback" not in source_path.parts
            ):
                raise OSError("synthetic config replacement failure")
            return real_replace(source, destination)

        with mock.patch.object(installer.os, "replace", side_effect=fail_config_commit):
            with self.assertRaisesRegex(installer.InstallerError, "rolled back"):
                installer.install(self.home)

        self.assertEqual(tree_snapshot(self.home), before)

    def test_clean_write_failure_removes_created_target_directories(self) -> None:
        installer = load_installer_module()
        real_replace = os.replace

        def fail_config_commit(source, destination):
            source_path = Path(source)
            destination_path = Path(destination)
            if (
                destination_path == self.home / "config.toml"
                and "rollback" not in source_path.parts
            ):
                raise OSError("synthetic clean-install failure")
            return real_replace(source, destination)

        with mock.patch.object(installer.os, "replace", side_effect=fail_config_commit):
            with self.assertRaisesRegex(installer.InstallerError, "rolled back"):
                installer.install(self.home)

        self.assertFalse(self.home.exists())


if __name__ == "__main__":
    unittest.main()
