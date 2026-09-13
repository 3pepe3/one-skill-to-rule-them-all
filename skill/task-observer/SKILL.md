---
name: task-observer
description: >-
  Use when a Codex session will call tools, execute a multi-step task, produce a deliverable, receive a reusable user correction, or discuss skill observations, skill improvement, the observation log, or a skill review.
---

# Task Observer

**Created by Eoghan Henn / [rebelytics.com](https://rebelytics.com).** This is
a Codex-native adaptation of
[One Skill to Rule Them All](https://github.com/rebelytics/one-skill-to-rule-them-all)
at commit `510caad26c907793e48306262af216ff9f71c9f7`. The adaptation retains the
upstream per-observation model, review safeguards, attribution, and CC BY 4.0
licence while specializing activation and tools for Codex.

**Licence:** CC BY 4.0. Share and adapt for any purpose with credit. The full
licence is in `LICENSE.txt`.

Observe real work for reusable ways to improve skills. Capture evidence while
it is fresh; never let observation work override the user's current task.

## Fixed installation boundary

The home skill is a generic observer for all projects. The central log is storage,
not authority to move project rules into global skills. Before selecting a fix
target, follow the scope routing in `references/review.md`: portable workflow
improvements may be global; project-specific rules belong to their canonical
project instructions, rule shards or skills. Application defects remain with
their application owners. Keep project names, paths and state out of generic
skill guidance; internal evidence and resolutions may retain exact local targets.

Resolve the Codex home as `${CODEX_HOME:-$HOME/.codex}` at runtime:

- Live skill: `${CODEX_HOME:-$HOME/.codex}/skills/task-observer`
- Mutable state: `${CODEX_HOME:-$HOME/.codex}/task-observer`
- Helper: `${CODEX_HOME:-$HOME/.codex}/skills/task-observer/scripts/task_observer.py`

Mutable state never belongs inside a skill-discovery directory. Resolve every
helper call with the fixed state root; do not derive it from the current
working directory.

## Session Start Protocol

Complete this before the first tool call. The user hook normally injects a
sanitized state summary, but loading this skill and executing the protocol are
separate requirements.

1. Determine whether the current context permits writes. `permission_mode:
   plan`, a read-only sandbox, a review-only request, or an explicit
   non-mutation instruction means **scan only**. Never initialize state, log,
   checkpoint, archive, update review dates, or stage skill changes in such a
   context.
2. In a mutable context, initialize idempotently:

   ```bash
   task_observer_codex_home="${CODEX_HOME:-$HOME/.codex}"
   python3 "$task_observer_codex_home/skills/task-observer/scripts/task_observer.py" \
     --state-root "$task_observer_codex_home/task-observer" init
   ```

   In a non-mutating context, use `status` or `scan`; add `--read-only` when
   invoking any command defensively. If state is absent, report deferred
   initialization and continue the user's task.
3. Run `scan`. It reads only active-record frontmatter. A nonzero exit or a
   positive `malformed` count is a broken scan, not a clean backlog; do not
   write until the malformed records are reconciled.
4. If open observations exist and `review_freshness` is `never` or `stale`,
   offer the review in one line and continue unless the user opts in. Mention
   pending staged updates in one line. Neither condition gates the user's task.
5. On the first empty installation, offer—but never start—a one-time history
   backfill over durable handover, decision, test, and commit records. Recurring
   review setup is also opt-in.

The `SessionStart` hook covers `startup`, `resume`, `clear`, and `compact`;
`SubagentStart` gives an optional collaborator the same state pointer. Optional
user-authorized `Stop` and `SessionEnd` automation is described in
`references/automation.md`. Hooks do not replace the checkpoints below.

## Observe throughout the task

Stay active during execution, feedback, review, and discussion of how work
should be done. Log when evidence suggests:

- a reusable workflow deserves a new skill;
- a user correction exposes a missing rule or edge case;
- a skill rule was violated, a better technique emerged, or tooling made a
  step obsolete;
- a skill contains unhelpful, contradictory, or repeatedly ignored guidance;
- a principle applies across related skills.

Do not log one-off task facts, preferences already captured, unrelated tool
failures, or material that cannot be generalized safely. When uncertain, read
`references/records.md` before deciding.

## Log immediately and silently

Create one file per observation in the same turn or the next. Before logging:

1. Confirm each `--skill` target exists. Otherwise use `--proposes-skill`.
2. Resolve the target in `skill-families.md`. If the registry has no match,
   inspect installed skill names for a related family.
3. Evaluate every sibling. Widen the target list when the principle is shared,
   then record the actual verdict in `--siblings-checked`. Use `none` only when
   no family exists.

Use the helper's `log --help` interface. It enforces the required metadata and
atomically reserves an ID and writes the record. A representative invocation
is in `references/records.md`.

Checkpoint to disk after roughly every third completed todo, on every major
deliverable or completed task batch, and before a deploy, release, publish, or
push. Log pending observations; if there are none, run:

```bash
task_observer_codex_home="${CODEX_HOME:-$HOME/.codex}"
python3 "$task_observer_codex_home/skills/task-observer/scripts/task_observer.py" \
  --state-root "$task_observer_codex_home/task-observer" \
  checkpoint --note "no observations"
```

In a non-mutating context, do not create even an empty checkpoint. A failed
write remains pending; report the failure accurately rather than calling it a
read-only log.

New records always start `status: open`. `parked` means the observation was
accepted but waits on a named external condition; it is outside the review
queue, requires `parked_until`, stays visible, and never archives. Full schema,
classification, atomicity, and archive rules are in `references/records.md`.

## Surface and act

Default to log-and-defer. At the task boundary, summarize records created this
session by ID and title, or say no observation was logged and why. Do not expose
observation bodies unless the user asks for the review.

Act during an explicit review, under recorded opt-in automation authority, on an
explicit request to act on a named observation, or when an in-session skill failure
is currently producing wrong output. Before any review, read `references/review.md`. Before creating or
editing a skill, read `references/skill-updates.md`.

Every skill change starts from a fresh copy of the complete live skill and is
written only under state-root staging. Never edit or replace a live skill
without explicit user approval, including applicable recorded automation
authorization. When work is applied, update each affected
observation's status in the same turn; multi-skill observations are not
actioned until every target has a recorded disposition.

Single-agent review is the complete authoritative workflow. If collaboration
tools are actually present and the apply phase is large, parallel work is only
an optimization: the parent owns observation statuses, merge decisions, and
combined verification. Never change persistent multi-agent configuration for
the observer.

## Pre-flight

Before delivering observer work:

- run `status` and reconcile counts with the files;
- confirm every new record has `status: open` and non-empty
  `siblings_checked`;
- confirm open-source principles contain no identifying project details;
- validate every staged full skill directory before presenting it;
- leave live skills untouched unless the user explicitly approves a specific
  staged replacement.

## Command reference

The helper provides `init`, `session-start`, `lifecycle`, `scan`, `log`, `checkpoint`,
`archive`, and `status`. Put `--state-root` before the command. Use
`--permission-mode plan` or `--read-only` to force non-mutation. Run the command
with `--help` for argument details.
