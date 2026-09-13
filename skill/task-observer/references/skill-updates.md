# Staging skill updates

Read this before creating or editing any skill from an observation. Observation
approval and live replacement are separate decisions.

An applicable explicit `root-review-and-install` authorization described in
`references/automation.md` covers both decisions within its recorded scope.
Complete-copy staging, validation, drift checks and backups remain required.

## Staging invariant

The live skill is the authority and is never the edit target. For each approved
target:

Use `exec_command` for read-only inventory, copying, diffs, and validation, and
use `apply_patch` for authored changes to the staged copy. When an approval
choice is genuinely required, use `request_user_input` if it is present in the
live tool surface; otherwise ask concisely in chat. Optional collaboration tools
do not change any permission or ownership boundary.

1. Freshly read the complete live skill directory.
2. Choose `${CODEX_HOME:-$HOME/.codex}/task-observer/skill-updates/YYYY-MM-DD/<skill-name>/`.
3. If that path already exists, diff it and integrate deliberately or report a
   conflict; never overwrite it based on time.
4. Recreate the directory structure and copy every regular file, including
   `SKILL.md`, `agents/`, `references/`, `scripts/`, and `assets/` where present.
   Make the staged copy user-writable.
5. Run `diff -rq <live> <staged>` and require identical output before editing.
6. Use `apply_patch` only against the staged path. Integrate guidance where it
   logically belongs; do not append a raw observation list.
7. Validate from a clean shell. Execute every embedded command against fixtures
   and inspect its output. For this skill, run:

   ```bash
   task_observer_codex_home="${CODEX_HOME:-$HOME/.codex}"
   python3 "$task_observer_codex_home/skills/task-observer/scripts/validate.py" \
     /absolute/staged/task-observer \
     --hooks-json "$task_observer_codex_home/hooks.json"
   PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s /absolute/staged/task-observer/tests -v
   ```

8. Append one manifest block to `skill-updates/PENDING.md` with this stable
   shape:

   ```markdown
   ## YYYY-MM-DD / skill-name
   - staged: /absolute/path/to/full/skill-directory
   - producer: session or scheduled-run identifier
   - observations: 12, 14
   - changes: #12 -> section -> rationale; #14 -> section -> rationale
   ```

9. Present the full staged directory path and a concise diff summary. Ask for
   explicit approval before replacing the named live directory. If approved,
   re-read live, confirm the staged base has not gone stale, install atomically,
   verify discovery in a fresh Codex session, then remove only that manifest
   entry. Without approval, leave staging and live state unchanged.

Keep only the two newest dated staged versions per skill, but pruning is a
separate destructive action: resolve exact paths and preserve any version still
named in `PENDING.md`.

## Authoring and family coherence

Match the skill's current structure, voice, and invocation policy. Keep
per-session decisions in `SKILL.md`; move episodic schemas, recipes, or large
inventories into focused references with explicit load triggers. Deterministic
rules belong in tested scripts when practical.

For a new member of a declared family, read every sibling before drafting and
record:

- shared content adopted;
- new shared content that must propagate, logged against every sibling;
- deliberately omitted member-specific content and why.

Follow the family's coherence model: edit each member for synced duplicates, or
edit the shared core and verify pointers for shared-core families.

## Attribution, licence, and confidentiality

Open-source skills retain creator attribution, source provenance, and the
selected licence. This adaptation must continue to credit Eoghan Henn, link the
upstream repository, identify that it is modified from commit
`510caad26c907793e48306262af216ff9f71c9f7`, and include `LICENSE.txt` with the
full CC BY 4.0 text.

Before staging an open-source change, sweep source observations and the draft
for user names, client names, domains, private paths, repository identifiers,
and examples whose combined details are re-identifying. Generalize or remove
them. A slightly broader example is safer than a traceable one. Internal records
stay internal and are never used in a public skill without a separate sanitized
derivation.

Methodology feedback may be drafted for the upstream repository only if the
user asks. Before any external contact, search existing issues and pull requests,
read the contribution preference, and verify the issue against current upstream
HEAD. Do not contact upstream, publish a fork, open an issue, or create a pull
request without explicit authorization.
