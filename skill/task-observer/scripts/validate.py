#!/usr/bin/env python3
"""Validate a staged Codex task-observer bundle and optional hook file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import sys
from typing import Any


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PATH_RE = re.compile(r"`((?:agents|references|scripts|tests)/[^`\s*?]+)`")
FORBIDDEN_RUNTIME_TERMS = re.compile(
    r"\b(?:" + "|".join(("clau" + "de", "cow" + "ork", "dis" + "patch")) + r")\b",
    re.IGNORECASE,
)


def leading_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing leading frontmatter delimiter")
    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError("missing closing frontmatter delimiter") from exc
    data: dict[str, str] = {}
    index = 1
    while index < closing:
        line = lines[index]
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not match:
            raise ValueError(f"unsupported frontmatter line: {line!r}")
        key, value = match.groups()
        if value in {">", ">-", "|", "|-"}:
            index += 1
            folded = []
            while index < closing and (not lines[index] or lines[index].startswith((" ", "\t"))):
                folded.append(lines[index].strip())
                index += 1
            data[key] = " ".join(part for part in folded if part)
            continue
        data[key] = value.strip().strip('"\'')
        index += 1
    return data, "\n".join(lines[closing + 1 :])


def check_skill(root: Path, failures: list[str]) -> None:
    skill_file = root / "SKILL.md"
    if not skill_file.is_file():
        failures.append("SKILL.md missing")
        return
    text = skill_file.read_text(encoding="utf-8")
    try:
        frontmatter, body = leading_frontmatter(text)
    except ValueError as exc:
        failures.append(f"frontmatter: {exc}")
        return
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if not NAME_RE.fullmatch(name):
        failures.append(f"frontmatter name is not kebab-case: {name!r}")
    elif name != root.name:
        failures.append(f"frontmatter name {name!r} does not match directory {root.name!r}")
    if not description:
        failures.append("frontmatter description missing")
    elif not description.startswith("Use when"):
        failures.append("frontmatter description must start with 'Use when'")
    elif len(description) > 1024:
        failures.append(f"frontmatter description exceeds 1024 characters: {len(description)}")
    if "Created by Eoghan Henn" not in body:
        failures.append("upstream creator attribution missing")
    if "510caad26c907793e48306262af216ff9f71c9f7" not in body:
        failures.append("adapted upstream commit attribution missing")
    if "CC BY 4.0" not in body:
        failures.append("CC BY 4.0 notice missing")
    for relative in sorted(set(PATH_RE.findall(text))):
        if not (root / relative).is_file():
            failures.append(f"referenced bundle file missing: {relative}")

    license_file = root / "LICENSE.txt"
    if not license_file.is_file():
        failures.append("LICENSE.txt missing")
    elif "Creative Commons Attribution 4.0 International Public License" not in license_file.read_text(
        encoding="utf-8"
    ):
        failures.append("LICENSE.txt is not the CC BY 4.0 full text")

    metadata = root / "agents" / "openai.yaml"
    if not metadata.is_file():
        failures.append("agents/openai.yaml missing")
    else:
        rendered = metadata.read_text(encoding="utf-8")
        required = (
            'display_name: "Task Observer"',
            "short_description:",
            "default_prompt:",
            "$task-observer",
            "allow_implicit_invocation: true",
        )
        for item in required:
            if item not in rendered:
                failures.append(f"agents/openai.yaml missing {item!r}")

    required_files = (
        "scripts/task_observer.py",
        "scripts/validate.py",
        "tests/test_task_observer.py",
        "references/records.md",
        "references/review.md",
        "references/skill-updates.md",
    )
    for relative in required_files:
        if not (root / relative).is_file():
            failures.append(f"required bundle file missing: {relative}")

    for script_path in sorted((root / "scripts").glob("*.py")):
        if not script_path.stat().st_mode & stat.S_IXUSR:
            failures.append(f"script is not user-executable: {script_path.relative_to(root)}")
        if ("import " + "yaml") in script_path.read_text(encoding="utf-8"):
            failures.append(f"third-party YAML dependency found: {script_path.relative_to(root)}")

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix in {".pyc", ".png", ".jpg", ".zip"}:
            continue
        try:
            rendered = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        match = FORBIDDEN_RUNTIME_TERMS.search(rendered)
        if match:
            failures.append(
                f"non-Codex runtime term {match.group(0)!r} in {path.relative_to(root)}"
            )
    junk = [
        path.relative_to(root)
        for path in root.rglob("*")
        if path.name in {"__pycache__", ".DS_Store"}
        or path.suffix == ".pyc"
        or path.name.startswith(".~lock")
    ]
    failures.extend(f"build artefact in bundle: {path}" for path in junk)


def iter_handlers(value: Any):
    if not isinstance(value, list):
        return
    for group in value:
        if not isinstance(group, dict):
            continue
        handlers = group.get("hooks")
        if isinstance(handlers, list):
            for handler in handlers:
                if isinstance(handler, dict):
                    yield group, handler


def check_hooks(path: Path, failures: list[str]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"hooks JSON invalid: {exc}")
        return
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        failures.append("hooks JSON lacks a hooks object")
        return
    observer_events: set[str] = set()
    for event, groups in hooks.items():
        for group, handler in iter_handlers(groups):
            command = str(handler.get("command", ""))
            if "task-observer/scripts/task_observer.py" not in command:
                continue
            observer_events.add(event)
            if event not in {"SessionStart", "SubagentStart"}:
                failures.append(f"task-observer command is configured for forbidden event {event}")
            if handler.get("type") != "command":
                failures.append(f"task-observer {event} handler must use type=command")
            if not command.endswith("session-start"):
                failures.append(f"task-observer {event} command must invoke session-start")
            limit = handler.get("additionalContextLimit")
            if not isinstance(limit, int) or limit <= 0:
                failures.append(f"task-observer {event} additionalContextLimit must be positive")
            if event == "SessionStart" and group.get("matcher") != "startup|resume|clear|compact":
                failures.append("task-observer SessionStart matcher is incomplete")
    missing = {"SessionStart", "SubagentStart"} - observer_events
    for event in sorted(missing):
        failures.append(f"task-observer {event} hook missing")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path)
    parser.add_argument("--hooks-json", type=Path)
    args = parser.parse_args(argv)
    root = args.skill_dir.resolve()
    failures: list[str] = []
    check_skill(root, failures)
    if args.hooks_json:
        check_hooks(args.hooks_json.resolve(), failures)
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PASS: task-observer bundle is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
