#!/usr/bin/env python3
"""Dependency-free state and hook helper for the Codex task-observer skill."""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from datetime import date, datetime, timezone
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterator


DEFAULT_CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
DEFAULT_STATE_ROOT = DEFAULT_CODEX_HOME / "task-observer"
VALID_STATUSES = ("open", "actioned", "declined", "superseded", "parked")
RESOLVED_STATUSES = {"actioned", "declined", "superseded"}
READ_ONLY_PERMISSION_MODES = {"plan"}
FRONTMATTER_LIMIT = 65_536
PRINCIPLES_TEMPLATE = """# Cross-Cutting Principles

Principles that apply to multiple skills. Read this as a mandatory checklist
when creating or regenerating a skill.

## Active Principles
"""


class ObserverError(RuntimeError):
    """A user-facing observer state error."""


def json_print(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, ensure_ascii=False))


def normalized_state_root(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def is_read_only(args: argparse.Namespace, event: dict[str, Any] | None = None) -> bool:
    if getattr(args, "read_only", False):
        return True
    mode = getattr(args, "permission_mode", None)
    if event and event.get("permission_mode"):
        mode = event["permission_mode"]
    return mode in READ_ONLY_PERMISSION_MODES


def make_dir(path: Path) -> bool:
    if path.is_dir():
        return False
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    return True


def create_text_once(path: Path, text: str) -> bool:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    return True


def atomic_replace_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_create_text(path: Path, text: str) -> None:
    """Install a complete new file atomically without overwriting a peer."""
    fd, temporary = tempfile.mkstemp(prefix=".observation.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        os.unlink(temporary)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def state_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    lock_path = root / ".observer.lock"
    with lock_path.open("a+", encoding="utf-8") as stream:
        try:
            os.chmod(lock_path, 0o600)
        except OSError:
            pass
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def ensure_layout(root: Path) -> bool:
    created = make_dir(root)
    created = make_dir(root / "observation-log") or created
    created = make_dir(root / "observation-log" / "archive") or created
    created = create_text_once(root / "last-review-date.txt", "never\n") or created
    created = create_text_once(
        root / "cross-cutting-principles.md", PRINCIPLES_TEMPLATE
    ) or created
    return created


def strip_inline_comment(value: str) -> str:
    if value.startswith(('"', "'", "[")):
        return value
    return re.sub(r"\s+#.*$", "", value).rstrip()


def parse_scalar(value: str) -> Any:
    value = strip_inline_comment(value.strip())
    if not value:
        return ""
    if value.startswith("["):
        if not value.endswith("]"):
            raise ObserverError("unterminated inline list")
        inner = value[1:-1].strip()
        if not inner:
            return []
        values = []
        for item in inner.split(","):
            item = item.strip()
            if not item:
                raise ObserverError("empty inline-list item")
            if item[:1] in {'"', "'"}:
                try:
                    item = ast.literal_eval(item)
                except (SyntaxError, ValueError) as exc:
                    raise ObserverError(f"invalid quoted value: {exc}") from exc
            values.append(str(item))
        return values
    if value[:1] in {'"', "'"}:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise ObserverError(f"invalid quoted value: {exc}") from exc
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    return value


def read_frontmatter(path: Path) -> dict[str, Any]:
    """Read only the leading frontmatter block, never the observation body."""
    result: dict[str, Any] = {}
    byte_count = 0
    with path.open("r", encoding="utf-8") as stream:
        first = stream.readline()
        byte_count += len(first.encode("utf-8"))
        if first.strip() != "---":
            raise ObserverError("missing leading frontmatter delimiter")
        for line in stream:
            byte_count += len(line.encode("utf-8"))
            if byte_count > FRONTMATTER_LIMIT:
                raise ObserverError("frontmatter exceeds 65536 bytes")
            if line.strip() == "---":
                return result
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$", line.rstrip("\n"))
            if not match:
                raise ObserverError(f"unsupported frontmatter line: {line.strip()!r}")
            key, raw = match.group(1), match.group(2) or ""
            if key in result:
                raise ObserverError(f"duplicate frontmatter key: {key}")
            result[key] = parse_scalar(raw)
    raise ObserverError("missing closing frontmatter delimiter")


def classified_status(frontmatter: dict[str, Any]) -> str:
    raw = str(frontmatter.get("status") or "").strip()
    return raw if raw in VALID_STATUSES[1:] else "open"


def read_review_state(root: Path) -> tuple[str, str | None, int | None]:
    path = root / "last-review-date.txt"
    if not path.is_file():
        return "missing", None, None
    value = path.read_text(encoding="utf-8").strip()
    if value == "never":
        return "never", value, None
    try:
        reviewed = date.fromisoformat(value)
    except ValueError:
        return "invalid", value, None
    age = (date.today() - reviewed).days
    return ("stale" if age > 7 else "fresh"), value, age


def pending_update_count(root: Path) -> int:
    pending = root / "skill-updates" / "PENDING.md"
    if not pending.is_file():
        return 0
    return sum(1 for line in pending.read_text(encoding="utf-8").splitlines() if line.startswith("## "))


def scan_state(root: Path, *, include_entries: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "state_root": str(root),
        "initialized": (root / "observation-log" / "archive").is_dir(),
        "files": 0,
        "parsed": 0,
        "malformed": 0,
        "records": 0,
        "open": 0,
        "actioned": 0,
        "declined": 0,
        "superseded": 0,
        "parked": 0,
        "missing_sibling_check": 0,
        "pending_updates": pending_update_count(root),
    }
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    log = root / "observation-log"
    paths = sorted(log.glob("*.md")) if log.is_dir() else []
    report["files"] = len(paths)
    for path in paths:
        try:
            frontmatter = read_frontmatter(path)
        except (OSError, UnicodeError, ObserverError) as exc:
            errors.append({"file": path.name, "error": str(exc)})
            continue
        status = classified_status(frontmatter)
        report["parsed"] += 1
        report["records"] += 1
        report[status] += 1
        siblings = frontmatter.get("siblings_checked")
        if not str(siblings or "").strip():
            report["missing_sibling_check"] += 1
        if include_entries:
            entries.append(
                {
                    "file": path.name,
                    "id": frontmatter.get("id"),
                    "title": frontmatter.get("title", ""),
                    "status": status,
                    "skill": frontmatter.get("skill", []),
                    "proposes_skill": frontmatter.get("proposes_skill", []),
                    "siblings_checked": siblings or "",
                }
            )
    report["malformed"] = len(errors)
    freshness, last_review, age = read_review_state(root)
    report["review_freshness"] = freshness
    report["last_review"] = last_review
    report["review_age_days"] = age
    report["review_due"] = bool(
        report["open"] and freshness in {"never", "stale", "missing", "invalid"}
    )
    if include_entries:
        report["entries"] = entries
        report["errors"] = errors
    return report


def replace_frontmatter_field(path: Path, key: str, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ObserverError(f"cannot update malformed record {path.name}")
    closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if closing is None:
        raise ObserverError(f"cannot update malformed record {path.name}")
    rendered = f"{key}: {value}\n"
    for index in range(1, closing):
        if re.match(rf"^{re.escape(key)}\s*:", lines[index]):
            lines[index] = rendered
            break
    else:
        lines.insert(closing, rendered)
    atomic_replace_text(path, "".join(lines))


def archive_locked(root: Path) -> dict[str, Any]:
    log = root / "observation-log"
    archive = log / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    dated: list[str] = []
    errors: list[dict[str, str]] = []
    today = date.today()
    for path in sorted(log.glob("*.md")):
        try:
            frontmatter = read_frontmatter(path)
            status = classified_status(frontmatter)
            if status not in RESOLVED_STATUSES:
                continue
            raw_resolved = str(frontmatter.get("resolved") or "").strip()
            try:
                resolved = date.fromisoformat(raw_resolved)
            except ValueError:
                replace_frontmatter_field(path, "resolved", today.isoformat())
                dated.append(path.name)
                continue
            if resolved >= today:
                continue
            destination = archive / path.name
            if destination.exists():
                raise ObserverError(f"archive destination already exists: {destination.name}")
            os.replace(path, destination)
            moved.append(path.name)
        except (OSError, UnicodeError, ObserverError) as exc:
            errors.append({"file": path.name, "error": str(exc)})
    return {
        "archived": len(moved),
        "dated": len(dated),
        "archived_files": moved,
        "dated_files": dated,
        "errors": errors,
    }


def highest_id(root: Path) -> int:
    log = root / "observation-log"
    values: list[int] = []
    for directory in (log, log / "archive"):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.md"):
            match = re.match(r"^([0-9]+)-", path.name)
            if match:
                values.append(int(match.group(1)))
    floor = log / "archive" / ".id-floor"
    if floor.is_file():
        raw = floor.read_text(encoding="utf-8").strip()
        if raw:
            try:
                values.append(int(raw))
            except ValueError as exc:
                raise ObserverError(".id-floor is not an integer") from exc
    active = list(log.glob("*.md")) if log.is_dir() else []
    if active and not values:
        raise ObserverError("active records exist but no observation id can be derived")
    return max(values, default=0)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:72].rstrip("-") or "observation"


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    return "[" + ", ".join(yaml_string(value) for value in values) + "]"


def render_observation(record_id: int, args: argparse.Namespace) -> str:
    reference = args.reference or ""
    return "\n".join(
        [
            "---",
            f"id: {record_id}",
            f"title: {yaml_string(args.title)}",
            "status: open",
            f"type: {args.type}",
            f"skill: {yaml_list(args.skill)}",
            f"proposes_skill: {yaml_list(args.proposes_skill)}",
            f"siblings_checked: {yaml_string(args.siblings_checked)}",
            f"area: {yaml_string(args.area)}",
            f"date: {date.today().isoformat()}",
            f"session_context: {yaml_string(args.session_context)}",
            "parked_until:",
            "resolved:",
            "resolution:",
            f"reference: {yaml_string(reference) if reference else ''}",
            "---",
            "",
            f"**Issue:** {args.issue}",
            "",
            f"**Suggested improvement:** {args.improvement}",
            "",
            f"**Principle:** {args.principle}",
            "",
        ]
    )


def deferred(root: Path, command: str) -> int:
    json_print(
        {
            "command": command,
            "created": False,
            "deferred": True,
            "initialized": (root / "observation-log" / "archive").is_dir(),
            "state_root": str(root),
        }
    )
    return 0


def command_init(args: argparse.Namespace) -> int:
    root = normalized_state_root(args.state_root)
    if is_read_only(args):
        return deferred(root, "init")
    with state_lock(root):
        created = ensure_layout(root)
    json_print({"created": created, "initialized": True, "state_root": str(root)})
    return 0


def command_scan(args: argparse.Namespace) -> int:
    root = normalized_state_root(args.state_root)
    report = scan_state(root, include_entries=True)
    json_print(report)
    return 1 if report["malformed"] else 0


def command_status(args: argparse.Namespace) -> int:
    root = normalized_state_root(args.state_root)
    json_print(scan_state(root, include_entries=False))
    return 0


def command_archive(args: argparse.Namespace) -> int:
    root = normalized_state_root(args.state_root)
    if is_read_only(args):
        return deferred(root, "archive")
    with state_lock(root):
        ensure_layout(root)
        report = archive_locked(root)
    report["state_root"] = str(root)
    json_print(report)
    return 1 if report["errors"] else 0


def command_log(args: argparse.Namespace) -> int:
    root = normalized_state_root(args.state_root)
    if is_read_only(args):
        return deferred(root, "log")
    if not args.skill and not args.proposes_skill:
        raise ObserverError("log requires --skill or --proposes-skill")
    if not args.siblings_checked.strip():
        raise ObserverError("--siblings-checked must not be blank")
    with state_lock(root):
        ensure_layout(root)
        archival = archive_locked(root)
        if archival["errors"]:
            raise ObserverError("archival failed before log write")
        record_id = highest_id(root) + 1
        floor = root / "observation-log" / "archive" / ".id-floor"
        atomic_replace_text(floor, f"{record_id}\n")
        path = root / "observation-log" / f"{record_id:04d}-{slugify(args.title)}.md"
        atomic_create_text(path, render_observation(record_id, args))
    json_print(
        {
            "created": True,
            "file": str(path),
            "id": record_id,
            "state_root": str(root),
        }
    )
    return 0


def command_checkpoint(args: argparse.Namespace) -> int:
    root = normalized_state_root(args.state_root)
    if is_read_only(args):
        return deferred(root, "checkpoint")
    note = " ".join(args.note.splitlines()).strip() or "no observations"
    with state_lock(root):
        ensure_layout(root)
        archival = archive_locked(root)
        if archival["errors"]:
            raise ObserverError("archival failed before checkpoint write")
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        fd = os.open(root / "checkpoints.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{timestamp} {note}\n")
            stream.flush()
            os.fsync(stream.fileno())
    json_print({"checkpointed": True, "note": note, "state_root": str(root)})
    return 0


def read_hook_event() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""
    if not raw.strip():
        return {}
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ObserverError(f"invalid hook JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise ObserverError("hook input must be a JSON object")
    return event


def command_session_start(args: argparse.Namespace) -> int:
    root = normalized_state_root(args.state_root)
    event = read_hook_event()
    event_name = event.get("hook_event_name")
    if event_name and event_name not in {"SessionStart", "SubagentStart"}:
        raise ObserverError(f"unsupported hook event: {event_name}")
    if event_name == "SessionStart" and event.get("source") not in {
        "startup",
        "resume",
        "clear",
        "compact",
    }:
        raise ObserverError(f"unsupported SessionStart source: {event.get('source')!r}")
    initialization = "ready"
    if is_read_only(args, event):
        initialization = "deferred" if not root.exists() else "read-only"
    else:
        try:
            with state_lock(root):
                ensure_layout(root)
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EROFS, errno.EPERM}:
                raise
            initialization = "deferred"
    report = scan_state(root, include_entries=False)
    parts = [
        "Task observer:",
        f"state={root};",
        f"records={report['records']};",
        f"open={report['open']};",
        f"parked={report['parked']};",
        f"malformed={report['malformed']};",
        f"review={report['review_freshness']};",
        f"pending_updates={report['pending_updates']};",
        f"initialization={initialization}.",
        "Invoke $task-observer before the first tool call and execute its Session Start Protocol.",
    ]
    if initialization in {"deferred", "read-only"}:
        parts.append("This context is non-mutating: scan existing state only and defer all writes.")
    elif event_name != "SubagentStart" and automation_enabled(root) and (report['open'] or report['pending_updates']):
        parts.append(AUTOMATIC_REVIEW_INSTRUCTION)
    print(" ".join(parts))
    return 0


AUTOMATIC_REVIEW_INSTRUCTION = (
    "Task-observer root-review-and-install is explicitly enabled by the user. "
    "Read automation.json and references/automation.md from the task-observer skill; "
    "review pending record bodies and classify scope before choosing targets: "
    "portable improvements go to generic global skills; project-specific fixes go to "
    "that project's canonical instructions, rules or skills, not the home observer. "
    "Apply supported improvements to the selected durable owners, "
    "validate staged copies and install with drift checks, then record dispositions. "
    "Use only this root thread; never launch another agent or edit plugin caches. "
    "Honor current read-only mode and user task constraints. Do not mark unapplied records actioned."
)


def automation_enabled(root: Path) -> bool:
    path = root / 'automation.json'
    if not path.exists():
        return False
    try:
        policy = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return False
    return isinstance(policy, dict) and policy.get('enabled') is True and policy.get('mode') == 'root-review-and-install'


def command_lifecycle(args: argparse.Namespace) -> int:
    root = normalized_state_root(args.state_root)
    event = read_hook_event()
    name = event.get('hook_event_name')
    if name not in {'Stop', 'SessionEnd', 'PreCompact'}:
        raise ObserverError('lifecycle requires Stop, SessionEnd or PreCompact')
    if is_read_only(args, event) or not automation_enabled(root) or event.get('stop_hook_active'):
        json_print({})
        return 0
    # Exit hooks are bounded to three seconds; never wait for a competing writer.
    with (root / '.observer.lock').open('a+', encoding='utf-8') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            json_print({})
            return 0
        report = scan_state(root, include_entries=True)
        if report['malformed'] or report['errors'] or report['missing_sibling_check']:
            raise ObserverError('observer records need repair before automatic review')
        if not report['open'] and not report['pending_updates']:
            json_print({})
            return 0
        digest = hashlib.sha256()
        for entry in report['entries']:
            if entry['status'] == 'open':
                digest.update((root / 'observation-log' / entry['file']).read_bytes())
        pending = root / 'skill-updates' / 'PENDING.md'
        if pending.exists():
            digest.update(pending.read_bytes())
        fingerprint = digest.hexdigest()
        atomic_replace_text(root / 'pending-review.json', json.dumps({
            'open': report['open'], 'pending_updates': report['pending_updates'],
            'fingerprint': fingerprint, 'event': name, 'status': 'review-required',
        }, sort_keys=True) + '\n')
        if name in {'SessionEnd', 'PreCompact'}:
            json_print({})
            return 0
        session = hashlib.sha256(str(event.get('session_id', 'unknown')).encode()).hexdigest()
        marker = root / 'lifecycle' / f'{session}.json'
        if marker.exists() and marker.read_text().strip() == fingerprint:
            json_print({})
            return 0
        atomic_replace_text(marker, fingerprint + '\n')
        json_print({'decision': 'block', 'reason': AUTOMATIC_REVIEW_INSTRUCTION})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Codex task-observer state without third-party dependencies."
    )
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--permission-mode", default=None)
    parser.add_argument("--read-only", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="initialize canonical observer state")
    commands.add_parser("session-start", help="process a Codex lifecycle-hook event from stdin")
    commands.add_parser("lifecycle", help="request root review on Stop or preserve pending work on SessionEnd")
    commands.add_parser("scan", help="scan active observation frontmatter only")
    commands.add_parser("status", help="report aggregate state and review freshness")
    commands.add_parser("archive", help="archive records resolved before today")

    log = commands.add_parser("log", help="atomically create one observation")
    log.add_argument("--title", required=True)
    log.add_argument("--type", choices=("open-source", "internal"), required=True)
    log.add_argument("--skill", action="append", default=[])
    log.add_argument("--proposes-skill", action="append", default=[])
    log.add_argument("--siblings-checked", required=True)
    log.add_argument("--area", required=True)
    log.add_argument("--session-context", required=True)
    log.add_argument("--issue", required=True)
    log.add_argument("--improvement", required=True)
    log.add_argument("--principle", required=True)
    log.add_argument("--reference")

    checkpoint = commands.add_parser("checkpoint", help="append a checkpoint acknowledgement")
    checkpoint.add_argument("--note", default="no observations")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "init": command_init,
        "session-start": command_session_start,
        "lifecycle": command_lifecycle,
        "scan": command_scan,
        "log": command_log,
        "checkpoint": command_checkpoint,
        "archive": command_archive,
        "status": command_status,
    }
    try:
        return handlers[args.command](args)
    except (ObserverError, OSError, UnicodeError) as exc:
        print(f"task-observer: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
