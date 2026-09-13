# Task Observer for Codex: User Guide

## Optional automatic application

Install with `python3 install.py --enable-auto-apply` to authorize review and
application within the recorded scope. Trust the new hooks in `/hooks`.
The `Stop` hook requests a review when work is pending. `PreCompact` and
`SessionEnd` preserve pending work for session activation to resume.
Project-specific rules stay in the owning project; reusable guidance goes to
global skills. Review includes staging, validation, backups and drift checks.
To disable, set `enabled` to `false` in your local
`task-observer/automation.json`, then rerun the installer without the option.

Task Observer is a background discipline for improving skills from real work.
It records reusable evidence while Codex completes the user's actual task, then
keeps review and live installation under explicit user control.

## Activation

The installer adds two lifecycle hooks:

- `SessionStart` for `startup`, `resume`, `clear`, and `compact`;
- `SubagentStart` for collaborators when that Codex capability is used.

Each hook emits a sanitised state summary and instructs Codex to invoke
`$task-observer` before its first tool call. Loading the skill and executing its
Session Start Protocol are separate requirements.

Hooks must be reviewed and trusted through `/hooks`. A hook that is new or has
changed is skipped until its exact definition is trusted.

## State locations

The live skill and mutable state are intentionally separate:

```text
$CODEX_HOME/skills/task-observer/   installed, discoverable skill
$CODEX_HOME/task-observer/          observations and review state
```

When `CODEX_HOME` is unset, both paths use `~/.codex`.

The mutable state contains:

```text
observation-log/                    active records
observation-log/archive/            eligible resolved records
skill-updates/                       complete staged skill directories
last-review-date.txt                 review freshness
cross-cutting-principles.md          accepted shared principles
checkpoints.log                      lightweight flush acknowledgements
```

Task Observer never stores mutable records inside its installed skill folder.

## Normal use

Work normally. Task Observer should remain quiet unless it needs a decision.
It logs evidence when a reusable workflow, user correction, missing skill,
skill failure, or cross-skill principle is observed. One-off task facts and
private project details do not belong in open-source observations.

Ask `What did Task Observer log?` when you want a summary. The assistant should
report record IDs and titles without exposing full bodies unless requested.

Check the current aggregate state directly with:

```bash
task_observer_codex_home="${CODEX_HOME:-$HOME/.codex}"
python3 "$task_observer_codex_home/skills/task-observer/scripts/task_observer.py" \
  --state-root "$task_observer_codex_home/task-observer" status
```

Run `--help` on the helper or an individual command for the complete interface.

## Observation lifecycle

New observations start as `open`. Review gives each record one of these final
or deferred states:

- `actioned`: its accepted change was completed;
- `declined`: the user chose not to apply it;
- `superseded`: another record or change replaced it;
- `parked`: accepted but waiting on a named external condition.

A parked record includes `parked_until`, remains visible, and is not archived.
Resolved records are archived only after their grace period, so current-day
review decisions remain easy to inspect.

Every record must contain sibling-check metadata. This forces review of related
skills before a supposedly local principle is treated as local.

## Reviews and skill updates

Ask Codex to `Run a Task Observer review` when you want to process open records.
Single-agent review is the complete workflow. Collaboration may speed up a
large review when available, but the parent session still owns status changes,
merge decisions, and combined verification.

An accepted skill update follows this boundary:

1. copy the complete live skill into a dated directory under
   `$CODEX_HOME/task-observer/skill-updates/`;
2. make and validate changes in that staged copy;
3. show the staged path and diff summary;
4. obtain explicit approval for the named replacement; and
5. atomically replace and verify the live skill.

Review never silently overwrites a live skill. If approval is not given, the
staged copy remains pending.

## Plan mode and read-only work

Task Observer treats `permission_mode: plan`, a read-only sandbox, a review-only
request, or an explicit non-mutation instruction as scan-only. It may inspect
existing frontmatter and report aggregate state, but it does not initialise,
log, checkpoint, archive, update review dates, or stage skill changes.

If state does not yet exist, the hook emits `initialization=deferred`. Start a
later mutable session to initialise it.

## Optional setup

History backfill is opt-in. On an empty first installation, you may ask Codex to
derive observations from durable handover, decision, test, and commit records.
Do not backfill private content into open-source observations without a separate
sanitised derivation.

Recurring review scheduling is also opt-in. Choose a cadence only after the
normal review workflow is useful to you; the skill does not create scheduled
tasks automatically.

## Troubleshooting

### The skill is installed but the hook does not run

Restart Codex, open `/hooks`, and inspect the Task Observer definitions. New or
changed non-managed hooks require explicit trust. Also confirm that
`[features].hooks` is not forced off by a higher-level policy.

### The scan reports malformed frontmatter

Treat a positive `malformed` count as a broken scan, not as an empty backlog.
Open only the named malformed records, repair their leading YAML metadata, then
run `scan` again. Do not log or archive while the active log is malformed.

### An installation fails

The installer validates existing JSON and TOML before target mutation. A
mid-write failure triggers rollback. Existing changed targets are copied under
`$CODEX_HOME/backups/task-observer/`; the reported backup path identifies the
recovery source.

### Validate the installed bundle

```bash
task_observer_codex_home="${CODEX_HOME:-$HOME/.codex}"
python3 "$task_observer_codex_home/skills/task-observer/scripts/validate.py" \
  "$task_observer_codex_home/skills/task-observer" \
  --hooks-json "$task_observer_codex_home/hooks.json"
```

Expected output: `PASS: task-observer bundle is valid`.
