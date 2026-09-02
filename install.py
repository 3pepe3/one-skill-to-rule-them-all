#!/usr/bin/env python3
"""Install the Codex Task Observer skill and lifecycle hooks safely."""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import filecmp
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
SOURCE_SKILL = REPO_ROOT / "skill" / "task-observer"
HOOK_TEMPLATE = REPO_ROOT / "codex" / "hooks.json.template"
VALIDATOR = SOURCE_SKILL / "scripts" / "validate.py"
OBSERVER_SCRIPT = Path("skills/task-observer/scripts/task_observer.py")
STATE_ROOT = Path("task-observer")
TABLE_HEADER_RE = re.compile(r"^\s*\[\[?([^\]]+)\]\]?\s*(?:#.*)?(?:\r?\n)?$")
HOOK_ASSIGNMENT_RE = re.compile(
    r"^(?P<indent>\s*)hooks(?P<spacing>\s*=\s*)"
    r"(?P<value>[^#\r\n]*?)(?P<suffix>\s*(?:#.*)?)(?P<newline>\r?\n)?$"
)


class InstallerError(RuntimeError):
    """A fail-closed installation error."""


@dataclass(frozen=True)
class InstallResult:
    changed: tuple[str, ...]
    backup: Path | None
    check: bool


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def validate_source_skill() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(SOURCE_SKILL)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stdout + result.stderr).strip()
        raise InstallerError(f"source skill validation failed: {detail}")


def _load_hook_template() -> dict[str, Any]:
    try:
        value = json.loads(HOOK_TEMPLATE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallerError(f"hook template is invalid: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("hooks"), dict):
        raise InstallerError("hook template is invalid: missing hooks object")
    return value


def render_observer_hooks(codex_home: Path) -> dict[str, Any]:
    codex_home = codex_home.resolve()
    command_values = {
        "__PYTHON__": shlex.quote(str(Path(sys.executable).resolve())),
        "__SKILL_SCRIPT__": shlex.quote(str(codex_home / OBSERVER_SCRIPT)),
        "__STATE_ROOT__": shlex.quote(str(codex_home / STATE_ROOT)),
    }

    def replace(value: Any) -> Any:
        if isinstance(value, str):
            for placeholder, rendered in command_values.items():
                value = value.replace(placeholder, rendered)
            return value
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    return replace(_load_hook_template())


def _is_observer_handler(handler: dict[str, Any]) -> bool:
    command = str(handler.get("command", ""))
    return "task-observer/scripts/task_observer.py" in command


def _validated_hooks(value: Any, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InstallerError(f"{path} is invalid: top level must be an object")
    hooks = value.get("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallerError(f"{path} is invalid: hooks must be an object")
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise InstallerError(f"{path} is invalid: hook events must contain arrays")
        for group in groups:
            if not isinstance(group, dict):
                raise InstallerError(f"{path} is invalid: hook groups must be objects")
            handlers = group.get("hooks", [])
            if not isinstance(handlers, list) or not all(
                isinstance(handler, dict) for handler in handlers
            ):
                raise InstallerError(f"{path} is invalid: handlers must be object arrays")
    return value


def merge_hooks(existing: dict[str, Any], observer: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(existing)
    merged.setdefault("description", observer.get("description"))
    merged_hooks = merged.setdefault("hooks", {})

    for event, groups in list(merged_hooks.items()):
        retained_groups = []
        for group in groups:
            original_handlers = group.get("hooks", [])
            retained_handlers = [
                handler for handler in original_handlers if not _is_observer_handler(handler)
            ]
            removed_observer = len(retained_handlers) != len(original_handlers)
            if retained_handlers or not removed_observer:
                retained = deepcopy(group)
                retained["hooks"] = retained_handlers
                retained_groups.append(retained)
        if retained_groups:
            merged_hooks[event] = retained_groups
        else:
            del merged_hooks[event]

    for event in ("SessionStart", "SubagentStart"):
        merged_hooks.setdefault(event, []).extend(deepcopy(observer["hooks"][event]))
    return merged


def _parse_toml(text: str, path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise InstallerError(f"{path} is invalid TOML: {exc}") from exc


def enable_hooks_feature(text: str) -> str:
    parsed = _parse_toml(text, Path("config.toml"))
    lines = text.splitlines(keepends=True)
    features_start: int | None = None
    features_end = len(lines)

    for index, line in enumerate(lines):
        match = TABLE_HEADER_RE.match(line)
        if not match:
            continue
        table = match.group(1).strip()
        if features_start is not None:
            features_end = index
            break
        if table == "features" and line.lstrip().startswith("["):
            features_start = index

    if features_start is None:
        prefix = text
        if prefix and not prefix.endswith(("\n", "\r")):
            prefix += "\n"
        if prefix and not prefix.endswith("\n\n"):
            prefix += "\n"
        rendered = prefix + "[features]\nhooks = true\n"
        _parse_toml(rendered, Path("config.toml"))
        return rendered

    assignment_index: int | None = None
    for index in range(features_start + 1, features_end):
        match = HOOK_ASSIGNMENT_RE.match(lines[index])
        if not match:
            continue
        assignment_index = index
        lines[index] = (
            f"{match.group('indent')}hooks{match.group('spacing')}true"
            f"{match.group('suffix')}{match.group('newline') or ''}"
        )
        break

    if assignment_index is None:
        if isinstance(parsed.get("features"), dict) and "hooks" in parsed["features"]:
            raise InstallerError("config.toml uses an unsupported quoted hooks key")
        newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
        lines.insert(features_end, f"hooks = true{newline}")

    rendered = "".join(lines)
    parsed_rendered = _parse_toml(rendered, Path("config.toml"))
    if parsed_rendered.get("features", {}).get("hooks") is not True:
        raise InstallerError("config.toml hooks feature could not be enabled")
    return rendered


def validate_existing_config(codex_home: Path) -> tuple[dict[str, Any], str]:
    hooks_path = codex_home / "hooks.json"
    config_path = codex_home / "config.toml"

    if hooks_path.exists():
        try:
            hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise InstallerError(f"{hooks_path} is invalid JSON: {exc}") from exc
        hooks = _validated_hooks(hooks, hooks_path)
    else:
        hooks = {"hooks": {}}

    if config_path.exists():
        try:
            config_text = config_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise InstallerError(f"cannot read {config_path}: {exc}") from exc
    else:
        config_text = ""
    _parse_toml(config_text, config_path)
    return hooks, config_text


def _same_tree(left: Path, right: Path) -> bool:
    if not left.is_dir() or not right.is_dir():
        return False
    comparison = filecmp.dircmp(left, right)
    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False
    if comparison.diff_files:
        return False
    return all(_same_tree(left / name, right / name) for name in comparison.common_dirs)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _copy_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def _prune_empty_parents(path: Path, stop: Path) -> None:
    current = path
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _commit_targets(
    targets: list[tuple[str, Path, Path]], temporary_root: Path
) -> None:
    rollback_root = temporary_root / "rollback"
    applied: list[tuple[Path, Path | None]] = []
    try:
        for name, staged, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            original: Path | None = None
            if target.exists() or target.is_symlink():
                original = rollback_root / name
                original.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, original)
            try:
                os.replace(staged, target)
            except BaseException:
                if original is not None:
                    os.replace(original, target)
                raise
            applied.append((target, original))
    except BaseException as exc:
        for target, original in reversed(applied):
            _remove_path(target)
            if original is not None and original.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(original, target)
        raise InstallerError(f"installation failed and was rolled back: {exc}") from exc


def install(codex_home: Path, check: bool = False) -> InstallResult:
    codex_home = codex_home.expanduser().resolve()
    validate_source_skill()
    existing_hooks, existing_config = validate_existing_config(codex_home)
    observer_hooks = render_observer_hooks(codex_home)
    merged_hooks = merge_hooks(existing_hooks, observer_hooks)
    hooks_text = json.dumps(merged_hooks, indent=2, ensure_ascii=False) + "\n"
    config_text = enable_hooks_feature(existing_config)

    parent = codex_home.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".task-observer-install-", dir=parent) as temporary:
        temporary_root = Path(temporary)
        staged_skill = temporary_root / "task-observer"
        shutil.copytree(SOURCE_SKILL, staged_skill)
        staged_hooks = temporary_root / "hooks.json"
        staged_config = temporary_root / "config.toml"
        _write_text(staged_hooks, hooks_text)
        _write_text(staged_config, config_text)

        state_target = codex_home / STATE_ROOT
        staged_state = temporary_root / "state"
        if not state_target.exists():
            helper = staged_skill / "scripts" / "task_observer.py"
            initialized = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    "--state-root",
                    str(staged_state),
                    "init",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if initialized.returncode:
                raise InstallerError(
                    "state initialisation failed: "
                    + (initialized.stdout + initialized.stderr).strip()
                )

        validation = subprocess.run(
            [
                sys.executable,
                str(staged_skill / "scripts" / "validate.py"),
                str(staged_skill),
                "--hooks-json",
                str(staged_hooks),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if validation.returncode:
            raise InstallerError(
                "staged installation validation failed: "
                + (validation.stdout + validation.stderr).strip()
            )

        skill_target = codex_home / "skills" / "task-observer"
        hooks_target = codex_home / "hooks.json"
        config_target = codex_home / "config.toml"
        targets: list[tuple[str, Path, Path]] = []
        if not _same_tree(staged_skill, skill_target):
            targets.append(("skill", staged_skill, skill_target))
        if not hooks_target.exists() or hooks_target.read_bytes() != staged_hooks.read_bytes():
            targets.append(("hooks", staged_hooks, hooks_target))
        if not config_target.exists() or config_target.read_bytes() != staged_config.read_bytes():
            targets.append(("config", staged_config, config_target))
        if not state_target.exists():
            targets.append(("state", staged_state, state_target))

        changed = tuple(name for name, _, _ in targets)
        if check:
            return InstallResult(changed=changed, backup=None, check=True)
        if not targets:
            return InstallResult(changed=(), backup=None, check=False)

        backup_root: Path | None = None
        existing_targets = [(name, target) for name, _, target in targets if target.exists()]
        if existing_targets:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            backup_root = codex_home / "backups" / "task-observer" / stamp
            for name, target in existing_targets:
                relative = {
                    "skill": Path("skills/task-observer"),
                    "hooks": Path("hooks.json"),
                    "config": Path("config.toml"),
                    "state": Path("task-observer"),
                }[name]
                _copy_backup(target, backup_root / relative)

        codex_home.mkdir(parents=True, exist_ok=True)
        try:
            _commit_targets(targets, temporary_root)
        except InstallerError:
            if backup_root is not None:
                _remove_path(backup_root)
                _prune_empty_parents(backup_root.parent, codex_home)
            raise
        return InstallResult(changed=changed, backup=backup_root, check=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=default_codex_home(),
        help="Codex home to update (default: CODEX_HOME or ~/.codex)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate and report required changes without modifying the Codex home",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = install(args.codex_home, check=args.check)
    except InstallerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if result.check:
        changes = ", ".join(result.changed) if result.changed else "none"
        print(f"Check passed; required changes: {changes}")
        return 0
    if result.changed:
        print("Installed Task Observer for Codex.")
        print("Changed: " + ", ".join(result.changed))
        if result.backup is not None:
            print(f"Backup: {result.backup}")
    else:
        print("Task Observer is already current; no files changed.")
    print("Open /hooks in Codex, review the new definitions, and trust them once.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
