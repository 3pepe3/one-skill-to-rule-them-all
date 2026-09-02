# Task Observer for Codex

Task Observer runs alongside tool-using Codex work and captures reusable
evidence for creating or improving skills. It keeps one Markdown file per
observation, supports deliberate review and staging, and never replaces a live
skill without explicit user approval.

This repository is the Codex-only adaptation of
[rebelytics/one-skill-to-rule-them-all](https://github.com/rebelytics/one-skill-to-rule-them-all)
at commit `510caad26c907793e48306262af216ff9f71c9f7`.

## What is included

- A global `$task-observer` skill with implicit invocation enabled.
- A dependency-free state helper with atomic concurrent observation logging.
- `SessionStart` hooks for startup, resume, clear, and compact events.
- A `SubagentStart` hook for Codex sessions that use collaborators.
- A conservative installer that merges configuration, creates backups, and
  rolls back a failed write.

There is no turn-end hook, network integration, telemetry, external service,
or automatic live-skill replacement.

## Requirements

- Codex with lifecycle-hook support.
- Python 3.11 or newer.
- A Unix-like environment. The generated hook commands use shell-safe absolute
  paths.

See the official OpenAI documentation for current
[skill discovery and metadata](https://learn.chatgpt.com/docs/build-skills) and
[hook configuration and trust](https://learn.chatgpt.com/docs/hooks).

## Install

```bash
git clone https://github.com/3pepe3/one-skill-to-rule-them-all.git
cd one-skill-to-rule-them-all
python3 install.py --check
python3 install.py
```

The installer resolves `$CODEX_HOME`, falling back to `~/.codex`. To install
into another isolated Codex home:

```bash
python3 install.py --codex-home /absolute/path/to/codex-home
```

Installation changes only these Task Observer surfaces:

- `$CODEX_HOME/skills/task-observer`
- `$CODEX_HOME/task-observer`
- Task Observer entries in `$CODEX_HOME/hooks.json`
- `[features].hooks = true` in `$CODEX_HOME/config.toml`

Unrelated hooks and configuration are retained. Existing changed targets are
backed up under `$CODEX_HOME/backups/task-observer/`. The installer does not
write approval policy, sandbox mode, models, MCP servers, plugins, project
trust, authentication, credentials, or hook trust hashes.

### Trust the hooks

Restart Codex after installation. Open `/hooks`, inspect the two Task Observer
definitions, and trust them once. Codex records trust against the exact hook
definition, so an updated command may require another review. The installer
does not bypass this safety boundary.

## Verify

```bash
task_observer_codex_home="${CODEX_HOME:-$HOME/.codex}"
python3 "$task_observer_codex_home/skills/task-observer/scripts/task_observer.py" \
  --state-root "$task_observer_codex_home/task-observer" status
```

The command returns aggregate counts and review freshness without observation
bodies or project content. In a new task-oriented Codex session, the startup
hook should also inject a short instruction to invoke `$task-observer` and run
its Session Start Protocol.

## Update

Pull this fork and run the installer again:

```bash
git pull --ff-only
python3 install.py --check
python3 install.py
```

Reinstallation is idempotent. If nothing changed, no target or backup is
rewritten. Existing observation state is preserved.

## Remove

Removal is deliberately manual so unrelated configuration cannot be guessed
away:

1. Open `$CODEX_HOME/hooks.json` and remove only the command handlers whose
   command points to `task-observer/scripts/task_observer.py`. Remove an empty
   Task Observer group after its handler is gone.
2. Remove `$CODEX_HOME/skills/task-observer` when the skill is no longer needed.
3. Keep `$CODEX_HOME/task-observer` if you may want the observation history;
   remove it only when you intentionally want to discard that state.
4. Keep `[features].hooks = true` if any other hooks remain. Otherwise you may
   remove that one setting.

Backups created by the installer can be used to restore pre-install versions.

## Documentation

- [User guide](USER-GUIDE.md)
- [Contributing](CONTRIBUTING.md)
- [Design specification](docs/superpowers/specs/2026-09-02-codex-task-observer-distribution-design.md)

## Attribution and licence

Task Observer was created by Eoghan Henn / [rebelytics.com](https://rebelytics.com).
This Codex adaptation retains the upstream observation model, review
safeguards, attribution, and CC BY 4.0 licence.

The complete licence is in [LICENSE.txt](LICENSE.txt).
