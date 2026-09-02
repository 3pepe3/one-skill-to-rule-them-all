# Observation records

Read this when deciding whether to log, creating a record, diagnosing a scan or
ID problem, changing a status, or archiving.

## Layout

```text
${CODEX_HOME:-$HOME/.codex}/task-observer/
  observation-log/
    0001-short-slug.md
    archive/
      .id-floor
  cross-cutting-principles.md
  skill-families.md
  last-review-date.txt
  checkpoints.log
  skill-updates/
    PENDING.md
```

The observation log is the directory, not a shared file. The directory listing
is its index. Active scans read only bytes between the first two `---` lines;
observation bodies are read only when resolving or reviewing a specific item.

## Frontmatter contract

| Field | Contract |
|---|---|
| `id` | Integer matching the filename prefix; never reused. |
| `title` | Short descriptive title. |
| `status` | `open`, `actioned`, `declined`, `superseded`, or `parked`. Missing, blank, and unknown values classify as open. |
| `type` | `open-source` or `internal`. |
| `skill` | Always a list of existing skills; first entry is primary. |
| `proposes_skill` | Always a list of candidate new skills. |
| `siblings_checked` | Mandatory and non-empty; family, members evaluated, and propagation verdict. `none` only means no family exists. |
| `area` | Affected part of the skill or workflow. |
| `date` | Date logged, `YYYY-MM-DD`. |
| `session_context` | Enough durable task context to understand the evidence. |
| `parked_until` | Mandatory yes/no condition when parked; empty otherwise. |
| `resolved` | Resolution date for actioned, declined, or superseded records. |
| `resolution` | What happened, including per-skill disposition where relevant. |
| `reference` | Optional durable path to evidence that would otherwise disappear. |

The body has exactly three semantic parts: Issue, Suggested improvement, and
Principle. The Principle is the generalizable claim. For an open-source record,
it must contain no client, domain, repository, or identifying project detail.

## Logging command

Validate the target and siblings before running the deterministic writer:

```bash
task_observer_codex_home="${CODEX_HOME:-$HOME/.codex}"
python3 "$task_observer_codex_home/skills/task-observer/scripts/task_observer.py" \
  --state-root "$task_observer_codex_home/task-observer" log \
  --title "Atomic reservation prevents duplicate IDs" \
  --type open-source \
  --skill task-observer \
  --siblings-checked "none" \
  --area "observation writer" \
  --session-context "concurrent helper validation" \
  --issue "Concurrent sessions could reserve the same numeric identifier." \
  --improvement "Allocate and write each observation while holding the state lock." \
  --principle "Shared counters require atomic reservation, not a max-then-write race."
```

Repeat `--skill` or `--proposes-skill` for multiple entries. Resolve each record
at its own write time; never pre-compute IDs for a batch. The helper takes an
exclusive state lock, advances `.id-floor` atomically, writes through a complete
temporary file, and installs without overwriting an existing path. A crash may
leave an unused ID, but cannot reuse one or truncate another record.

## What qualifies

Ask four questions:

1. Would this still matter in another project?
2. Would another task using the same skill encounter it?
3. Does it name a missing rule, step, or principle rather than merely fix this
   task?
4. Is recurrence plausible or evidenced?

Mostly no means task context, not an observation. Positive evidence and
simplification count too: a technique that worked reliably may become guidance;
a never-used or contradictory section may be removed. Do not turn one user's
local preference into a universal rule.

## Families and sibling checks

When related skills share methodology, create `skill-families.md` only after a
real family is identified:

```markdown
## family-name
**Members:** skill-a, skill-b
**Coherence model:** synced-duplicates | shared-core
**Shared:** material every member must carry
**Member-specific:** legitimate differences and why
```

Before every log, evaluate the target against this registry. With no registry
match, scan installed names for shared subject, prefix, suffix, or companion
patterns. A rule that remains true after removing the tool or subject name is a
strong propagation signal. Record both propagation and justified
instance-specific verdicts; the metadata makes a performed check distinguishable
from an omitted one.

## Status and archival

- `open`: awaiting review.
- `actioned`: applied or confirmed already present.
- `declined`: reviewed and intentionally rejected.
- `superseded`: replaced by a later record; the resolution names its ID.
- `parked`: accepted but blocked on `parked_until`; excluded from work queue and
  archival until genuinely resolved.

Before changing an existing record, re-read that file. Edit only `status`,
`parked_until`, `resolved`, and `resolution`; never rewrite the directory.

Every mutating helper command performs archival first. Actioned, declined, and
superseded records with a `resolved` date before today move individually to
`archive/`. Same-day resolutions remain visible for a cross-session grace
period. A resolved status with an absent or invalid date is dated today and left
active. Parked records never archive. Run `archive` explicitly to inspect its
machine-readable result.

An empty scan over known files or a nonzero `malformed` count is a stop signal.
Re-probe the layout and the named files. Never create a replacement structure
on the assumption that empty output means an empty backlog.
