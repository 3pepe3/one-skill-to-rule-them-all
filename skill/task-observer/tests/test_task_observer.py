#!/usr/bin/env python3
"""Behavior tests for the dependency-free task-observer CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / "scripts" / "task_observer.py"
VALIDATOR = SKILL_ROOT / "scripts" / "validate.py"


def run_cli(*args: str, event: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        input=(json.dumps(event) if event is not None else None),
        text=True,
        capture_output=True,
        check=False,
    )


def write_record(
    root: Path,
    record_id: int,
    *,
    title: str = "Fixture title",
    status: str | None = "open",
    resolved: str = "",
    siblings_checked: str | None = "none",
    parked_until: str = "",
    body: str = "fixture body",
) -> Path:
    log = root / "observation-log"
    log.mkdir(parents=True, exist_ok=True)
    (log / "archive").mkdir(exist_ok=True)
    fields = [
        "---",
        f"id: {record_id}",
        f"title: {title}",
    ]
    if status is not None:
        fields.append(f"status: {status}")
    fields.extend(
        [
            "type: open-source",
            "skill: [task-observer]",
            "proposes_skill: []",
        ]
    )
    if siblings_checked is not None:
        fields.append(f"siblings_checked: {siblings_checked}")
    fields.extend(
        [
            "area: testing",
            f"date: {date.today().isoformat()}",
            "session_context: fixture",
            f"parked_until: {parked_until}",
            f"resolved: {resolved}",
            "resolution:",
            "reference:",
            "---",
            "",
            f"**Issue:** {body}",
            "",
            "**Suggested improvement:** fixture improvement",
            "",
            "**Principle:** fixture principle",
            "",
        ]
    )
    path = log / f"{record_id:04d}-fixture-{record_id}.md"
    path.write_text("\n".join(fields), encoding="utf-8")
    return path


class ObserverCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def init(self) -> dict:
        result = run_cli("--state-root", str(self.root), "init")
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def status(self) -> dict:
        result = run_cli("--state-root", str(self.root), "status")
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def log_args(self, title: str) -> list[str]:
        return [
            "--state-root",
            str(self.root),
            "log",
            "--title",
            title,
            "--type",
            "open-source",
            "--skill",
            "task-observer",
            "--siblings-checked",
            "none",
            "--area",
            "testing",
            "--session-context",
            "unit test",
            "--issue",
            "A repeatable issue occurred.",
            "--improvement",
            "Add the missing guard.",
            "--principle",
            "Concurrent writers need atomic allocation.",
        ]

    def test_default_state_root_uses_codex_home(self) -> None:
        codex_home = Path(self.temp.name) / "custom-codex"
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(codex_home)

        result = subprocess.run(
            [sys.executable, str(CLI), "status"],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(
            json.loads(result.stdout)["state_root"],
            str((codex_home / "task-observer").resolve()),
        )
        self.assertFalse(codex_home.exists())

    def test_init_creates_only_canonical_state_and_is_idempotent(self) -> None:
        first = self.init()
        second = self.init()
        self.assertTrue(first["initialized"])
        self.assertFalse(second["created"])
        self.assertTrue((self.root / "observation-log" / "archive").is_dir())
        self.assertEqual((self.root / "last-review-date.txt").read_text().strip(), "never")
        self.assertTrue((self.root / "cross-cutting-principles.md").is_file())
        self.assertFalse((self.root / "skill-families.md").exists())

    def test_plan_and_read_only_modes_never_initialize_or_log(self) -> None:
        event = {
            "hook_event_name": "SessionStart",
            "source": "startup",
            "permission_mode": "plan",
            "cwd": "/private/project",
            "session_id": "secret-session",
        }
        started = run_cli("--state-root", str(self.root), "session-start", event=event)
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("initialization=deferred", started.stdout)
        self.assertFalse(self.root.exists())

        logged = run_cli(
            "--state-root",
            str(self.root),
            "--permission-mode",
            "plan",
            *self.log_args("deferred")[2:],
        )
        self.assertEqual(logged.returncode, 0, logged.stderr)
        self.assertIn("deferred", logged.stdout)
        self.assertFalse(self.root.exists())

        checkpoint = run_cli(
            "--state-root",
            str(self.root),
            "--read-only",
            "checkpoint",
            "--note",
            "must not exist",
        )
        self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)
        self.assertFalse(self.root.exists())

    def test_concurrent_logging_allocates_unique_ids_and_files(self) -> None:
        self.init()
        processes = []
        for number in range(24):
            processes.append(
                subprocess.Popen(
                    [sys.executable, str(CLI), *self.log_args(f"Concurrent {number}")],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            )
        outputs = [process.communicate(timeout=30) for process in processes]
        for process, (stdout, stderr) in zip(processes, outputs):
            self.assertEqual(process.returncode, 0, stderr or stdout)
        records = sorted((self.root / "observation-log").glob("*.md"))
        self.assertEqual(len(records), 24)
        ids = [int(path.name.split("-", 1)[0]) for path in records]
        self.assertEqual(ids, list(range(1, 25)))
        self.assertEqual(
            (self.root / "observation-log" / "archive" / ".id-floor").read_text().strip(),
            "24",
        )
        titles = {line for path in records for line in path.read_text().splitlines() if line.startswith("title:")}
        self.assertEqual(len(titles), 24)

    def test_logging_requires_sibling_metadata_and_a_target(self) -> None:
        self.init()
        args = self.log_args("Missing sibling check")
        index = args.index("--siblings-checked")
        del args[index : index + 2]
        result = run_cli(*args)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list((self.root / "observation-log").glob("*.md")), [])

        args = self.log_args("Missing target")
        index = args.index("--skill")
        del args[index : index + 2]
        result = run_cli(*args)
        self.assertNotEqual(result.returncode, 0)

    def test_scan_reports_malformed_frontmatter_instead_of_clean_backlog(self) -> None:
        self.init()
        malformed = self.root / "observation-log" / "0001-malformed.md"
        malformed.write_text("title: not frontmatter\nSECRET BODY\n", encoding="utf-8")
        result = run_cli("--state-root", str(self.root), "scan")
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["files"], 1)
        self.assertEqual(report["parsed"], 0)
        self.assertEqual(report["malformed"], 1)
        self.assertNotIn("SECRET BODY", result.stdout)

    def test_status_classifies_missing_unknown_and_parked_records(self) -> None:
        self.init()
        write_record(self.root, 1, status="open")
        write_record(self.root, 2, status=None)
        write_record(self.root, 3, status="unexpected", siblings_checked=None)
        write_record(self.root, 4, status="actioned", resolved=date.today().isoformat())
        write_record(self.root, 5, status="declined", resolved=date.today().isoformat())
        write_record(self.root, 6, status="superseded", resolved=date.today().isoformat())
        write_record(self.root, 7, status="parked", parked_until="dependency lands")
        report = self.status()
        self.assertEqual(report["records"], 7)
        self.assertEqual(report["open"], 3)
        self.assertEqual(report["actioned"], 1)
        self.assertEqual(report["declined"], 1)
        self.assertEqual(report["superseded"], 1)
        self.assertEqual(report["parked"], 1)
        self.assertEqual(report["missing_sibling_check"], 1)

    def test_archive_keeps_today_and_parked_but_moves_prior_resolutions(self) -> None:
        self.init()
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        write_record(self.root, 1, status="actioned", resolved=today)
        write_record(self.root, 2, status="actioned", resolved=yesterday)
        write_record(self.root, 3, status="declined", resolved="")
        write_record(self.root, 4, status="superseded", resolved=yesterday)
        write_record(self.root, 5, status="parked", resolved=yesterday, parked_until="external event")
        result = run_cli("--state-root", str(self.root), "archive")
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["archived"], 2)
        self.assertEqual(report["dated"], 1)
        active = {path.name for path in (self.root / "observation-log").glob("*.md")}
        archived = {path.name for path in (self.root / "observation-log" / "archive").glob("*.md")}
        self.assertEqual(active, {"0001-fixture-1.md", "0003-fixture-3.md", "0005-fixture-5.md"})
        self.assertEqual(archived, {"0002-fixture-2.md", "0004-fixture-4.md"})
        self.assertIn(f"resolved: {today}", (self.root / "observation-log" / "0003-fixture-3.md").read_text())

    def test_id_floor_survives_an_empty_active_log(self) -> None:
        self.init()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        write_record(self.root, 1, status="actioned", resolved=yesterday)
        (self.root / "observation-log" / "archive" / ".id-floor").write_text("1\n")
        archived = run_cli("--state-root", str(self.root), "archive")
        self.assertEqual(archived.returncode, 0, archived.stderr)
        logged = run_cli(*self.log_args("After archive"))
        self.assertEqual(logged.returncode, 0, logged.stderr)
        self.assertEqual(json.loads(logged.stdout)["id"], 2)

    def test_review_freshness_and_pending_updates_are_machine_classified(self) -> None:
        self.init()
        report = self.status()
        self.assertEqual(report["review_freshness"], "never")

        (self.root / "last-review-date.txt").write_text(
            (date.today() - timedelta(days=8)).isoformat() + "\n", encoding="utf-8"
        )
        self.assertEqual(self.status()["review_freshness"], "stale")

        (self.root / "last-review-date.txt").write_text(
            (date.today() - timedelta(days=2)).isoformat() + "\n", encoding="utf-8"
        )
        pending = self.root / "skill-updates" / "PENDING.md"
        pending.parent.mkdir(parents=True)
        pending.write_text(
            "# Pending skill updates\n\n## 2026-09-01 / alpha\nbody\n\n## 2026-09-02 / beta\nbody\n",
            encoding="utf-8",
        )
        report = self.status()
        self.assertEqual(report["review_freshness"], "fresh")
        self.assertEqual(report["pending_updates"], 2)

    def test_checkpoint_appends_without_rewriting_existing_lines(self) -> None:
        self.init()
        for note in ("first", "second"):
            result = run_cli(
                "--state-root", str(self.root), "checkpoint", "--note", note
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / "checkpoints.log").read_text(encoding="utf-8")
        self.assertIn("first", text)
        self.assertIn("second", text)
        self.assertLess(text.index("first"), text.index("second"))

    def test_hook_fixtures_are_sanitized_for_all_supported_events(self) -> None:
        self.init()
        write_record(self.root, 1, title="DO NOT LEAK THIS TITLE", body="DO NOT LEAK BODY")
        for event_name, source in (
            ("SessionStart", "startup"),
            ("SessionStart", "resume"),
            ("SessionStart", "clear"),
            ("SessionStart", "compact"),
            ("SubagentStart", None),
        ):
            event = {
                "hook_event_name": event_name,
                "permission_mode": "default",
                "cwd": "/private/customer/project",
                "session_id": "secret-session",
                "agent_id": "secret-agent",
            }
            if source:
                event["source"] = source
            result = run_cli("--state-root", str(self.root), "session-start", event=event)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"state={self.root}", result.stdout)
            self.assertIn("records=1", result.stdout)
            self.assertIn("Invoke $task-observer", result.stdout)
            self.assertNotIn("DO NOT LEAK", result.stdout)
            self.assertNotIn("/private/customer", result.stdout)
            self.assertNotIn("secret-session", result.stdout)
            self.assertNotIn("secret-agent", result.stdout)

    def test_validator_accepts_supported_hooks_and_rejects_stop(self) -> None:
        hook_file = Path(self.temp.name) / "hooks.json"
        valid = {
            "description": "Task observer lifecycle activation.",
            "hooks": {
                "SessionStart": [
                    {
                        "matcher": "startup|resume|clear|compact",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"/usr/bin/python3 {CLI} --state-root /tmp/state session-start",
                                "additionalContextLimit": 500,
                            }
                        ],
                    }
                ],
                "SubagentStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"/usr/bin/python3 {CLI} --state-root /tmp/state session-start",
                                "additionalContextLimit": 500,
                            }
                        ]
                    }
                ],
            },
        }
        hook_file.write_text(json.dumps(valid), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(SKILL_ROOT), "--hooks-json", str(hook_file)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        valid["hooks"]["Stop"] = valid["hooks"]["SubagentStart"]
        hook_file.write_text(json.dumps(valid), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(SKILL_ROOT), "--hooks-json", str(hook_file)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Stop", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
