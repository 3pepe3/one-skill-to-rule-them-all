---
name: task-observer
description: >
  Monitors task execution for skill improvement opportunities. Use this skill
  during ANY multi-step task, agentic workflow, or substantive work session where
  the agent is using tools and producing deliverables. It captures patterns, user
  corrections, workflow insights, and methodology worth preserving as reusable
  skills. Also triggers during post-task feedback discussions and when the user
  explicitly mentions skill observations, improvements, the observation log,
  skill taxonomy, or asks the agent to watch for skill opportunities. Also known
  as "One Skill to Rule Them All" — trigger on this phrase too. IMPORTANT:
  this skill should be invoked at the start of every task-oriented session — if
  you are about to use tools to produce deliverables, invoke this skill first.
  For reliable activation, pair this description with a CLAUDE.md instruction
  or harness-level session-start hook (see Recommended Activation Setup) —
  description-level matching alone is not enforceable.
---

# Task Observer — Continuous Skill Discovery & Improvement

**Created by Eoghan Henn / [rebelytics.com](https://rebelytics.com)** —
*"One Skill to Rule Them All."* Licensed CC BY 4.0: share and adapt freely
with credit to the author. Methodology feedback → suggest an issue at
[github.com/rebelytics/one-skill-to-rule-them-all](https://github.com/rebelytics/one-skill-to-rule-them-all);
if the problem is the agent not following the skill's rules, acknowledge and
correct it instead.

Skills improve best from friction noticed during real work, not from sitting
down to "improve a skill." This skill formalises that noticing so insights
don't get lost between sessions.

`[workspace folder]` = the persistent workspace (project root in Claude
Code). The observation log lives at
`[workspace folder]/skill-observations/log.md` unless the user's
configuration pins it elsewhere.

## Reference files — load on demand, not up front

- `references/weekly-review.md` — the comprehensive review procedure
  (scheduled or 7-day fallback), approval policy, delivery/staging of
  updated skills. Load when a review triggers or the user asks for one.
- `references/skill-authoring.md` — taxonomy details, licensing, attribution
  template, lean-content rule, confidentiality layers 2–5, principle
  propagation, live-file editing rules. Load before creating or editing any
  skill.
- `references/environments.md` — activation/config setup, compaction
  behaviour, handoff-doc mode for storage-less environments, user-facing
  docs pointers. Load for setup questions or when there's no filesystem.

## Session Start Protocol

1. If `skill-observations/log.md` or `cross-cutting-principles.md` don't
   exist, create them (templates below / in the principles section of
   `references/skill-authoring.md`).
2. Scan OPEN observations and active principles; hold them in awareness,
   don't surface unprompted.
3. Read `skill-observations/last-review-date.txt`. Missing or older than 7
   days → load `references/weekly-review.md` and run the review before the
   user's task. Otherwise proceed.
4. Once per session: if no CLAUDE.md (or equivalent) activation instruction
   for this skill exists, briefly suggest adding one (see
   `references/environments.md`). Skip if already configured.
5. Note the log's modification time. If modified in the last few hours,
   another session may be writing to it — re-read immediately before every
   append, never trust a remembered "current number".

## When to Observe

Active for the entire task session: execution, post-task feedback and
review discussion, meta-discussion about skills or methodology, and
reflective/strategy conversations about how work should be done. **The
observation mindset does not deactivate when the conversation shifts from
doing the work to discussing it** — user feedback in review phases is often
the highest-signal input. Inactive only for casual conversation and quick
factual questions with no tools or deliverables involved.

## What to Watch For

**Signals for a NEW skill:** a reusable multi-step workflow; a methodology
the user explains that no existing skill captures; a recurring task type
with similar structure; a process with clear inputs, phases, outputs; the
user describing a refined process ("I always do it this way"); a structured
approach emerging naturally during work.

**Signals for IMPROVING an existing skill:** anything from a task that used
a skill and could make it better — problems, positive signals, or neutral
gaps. Examples: the agent violates a documented rule (the skill needs
enforcement, not louder rules); a user correction reveals a missing rule or
edge case; a better workflow emerges than the skill recommends; a technique
works well enough to promote from incidental to recommended; an undocumented
use case; feedback that generalises; a wrong assumption; new tooling
obsoletes a step; corrections forming a pattern; a principle that applies to
other skills too; a naming/framing/structural suggestion, even
conversational.

**Signals for SIMPLIFYING a skill:** a section never relevant across many
sessions; a rule from a single unvalidated observation; workflows users
consistently shortcut; sections loaded but never acted on; contradictory
rules; "just in case" complexity that never triggered; a rule the agent
consistently fails to follow (convert to structural enforcement — checklist,
verification step, unskippable tool call — or remove it). Treat these as a
review checklist; ask "what can we remove?" as deliberately as "what should
we add?"

**Do NOT log:** one-off corrections that don't generalise; preferences
already captured in a skill; tool bugs unrelated to methodology;
observations that would need proprietary client information to be useful in
an open-source skill (unless an internal skill is the right home).

## How to Log

Append to the log **silently, within the same turn or the next** — never
batch mentally for later; the act of writing is the enforcement mechanism.

**Mandatory observation checkpoint after every 3rd TodoWrite completion:** After
marking the 3rd, 6th, 9th (etc.) TodoWrite item as completed in a session, you
must **write to the log** — not merely pause to ask yourself a question. Either
append any pending observations, or, if genuinely none have accumulated, append
an explicit acknowledgement marker (a one-line `no observations` note for that
checkpoint). The required action is a concrete log write; a remembered "ask
whether" is not enforcement. This is a hard checkpoint, not a suggestion — the
skill has demonstrated that softer "check when completing items" or "pause and
ask" guidance gets lost during cognitively demanding analytical work, exactly
when the most observations accumulate. The count doesn't need to be precise;
the rule is: roughly every third completion, write to the log (observations or
the acknowledgement marker). The write itself is the enforcement mechanism: it
forces the mental check to surface as a recorded action, and it prevents the
common failure mode where the skill is loaded but no observations are written
until the user explicitly asks.

**Deliverable-event flush:** Hard enforcement that hooks onto tool calls you are
already making is the only reliable mechanism; soft prompts that rely on memory
don't survive cognitive load during long substantive sessions (when the most
insights surface). So tie observation-flushing to deliverable and workflow events
that already involve a tool call. Whenever you present or render a major
deliverable — `present_files`, a deck or PDF render, a staged skill file handed
to the user — or complete a task/todo batch, flush any pending observations to
the log at that moment, before moving on. These are natural, already-occurring
checkpoints; piggy-backing the flush onto them means the write happens as a
side effect of work you were doing anyway, rather than depending on a separate
act of memory.

**Numbering discipline (mandatory, every append):**

1. *Pre-check:* read the actual log and find the highest existing number —
   never trust session memory:

   ```bash
   # GNU grep:
   grep -oP '### Observation \K\d+' log.md | sort -n | tail -1
   # macOS / POSIX:
   grep -o '### Observation [0-9]*' log.md | grep -o '[0-9]*' | sort -n | tail -1
   ```

2. *Pre-write assertion:* immediately before appending, confirm the proposed
   number doesn't already exist:

   ```bash
   PROPOSED=$(( $(grep -oP '### Observation \K\d+' log.md | sort -n | tail -1) + 1 ))
   grep -qE "^### Observation ${PROPOSED}:" log.md && {
     echo "COLLISION on #${PROPOSED}"; exit 1; }
   ```

   If it fires, increment past all existing numbers and re-check (and log a
   meta-observation — it signals a parallel-session collision).

3. *Post-write verification:* after appending, count occurrences of the
   number; if >1, a parallel writer collided between check and write —
   renumber your entry (the last occurrence) to max+1 via `sed`. Pre-write
   catches stale reads; only a post-write check catches the race. The
   pattern for shared logs written by parallel agents is
   check-then-act-then-verify.

**Log-write safety — never let a mutation span entry boundaries:** When
mutating the log programmatically (marking entries ACTIONED/DECLINED,
archiving, renumbering), a greedy or DOTALL pattern over the whole file can
silently swallow everything from one match to EOF. This has happened: a
`.*$` under `re.S` over the multi-entry file captured from one entry's
Status line to end-of-file and overwrote 16 later entries in a single
substitution. The log is shared state across many entries; mutate it one
bounded entry at a time and verify every mutation.

1. **Isolate the target entry, or anchor to a single line.** Either split
   the log on `### Observation N:` headers, edit the TARGET entry's chunk in
   isolation, and reassemble — OR, for a status-only edit, use a strictly
   line-anchored multiline substitution that cannot cross a newline, e.g.
   `re.sub(r'(?m)^(\s*-?\s*)\*\*Status:\*\*.*$', ...)` (multiline `^...$`
   bounds the match to one line). NEVER use a DOTALL/greedy pattern across
   the multi-entry file.

2. **Assert a structural invariant after every write.** Count
   `### Observation` headers before and after the mutation. For a status-only
   edit the count MUST be unchanged; for archival or append it must change by
   exactly the expected number. Fail loudly if the count is off — a silent
   mismatch means the write captured more than its target.

3. **Keep the pre-write backup.** Copy `log.md` before any programmatic
   mutation. This is what made full recovery trivial when the truncation
   above occurred — it turned a destructive bug into a non-event.

Principle: a log shared across many entries must be mutated one bounded
entry at a time, and every mutation verified by a structural invariant
(entry count) immediately afterwards. Backups turn a destructive bug into a
non-event.

**Format and insertion:** always `### Observation NNN:`, always appended to
the END of the log, never mid-file, never alternative ID formats. One
format, one insertion point. **Every new observation MUST include
`**Status:** OPEN` as its first field — this is mandatory at write time, not
optional.** Reviews classify entries by their Status line; an observation
written without one is invisible to any status-filtered pass and risks being
silently skipped instead of triaged.

```markdown
### Observation [N]: [Short descriptive title]

**Status:** OPEN
**Date:** [date]
**Session context:** [what task was being worked on]
**Skill:** [existing skill name, or "New skill candidate: [working name]"]
**Type:** [open-source | internal]
**Phase/Area:** [which part of the skill or workflow]

**Issue:** [What happened — specific enough to understand weeks later
without the original conversation.]

**Suggested improvement:** [Concrete change. For existing skills, name the
section or rule; for new skills, scope and key components.]

**Principle:** [The generalisable takeaway — the most important field.]
```

**Context preservation:** if an observation depends on session-local data
(uploads, API output), save that context into the workspace first and add a
`**Reference file:**` line — an observation whose evidence dies with the
session is incomplete.

**Confidentiality at logging time:** for `type: open-source` observations,
the Issue/Improvement fields may reference specifics for context, but the
Principle must be fully generalised — no client names, domains, or details
traceable to a real project. Full confidentiality layers for skill
authoring: `references/skill-authoring.md`.

## Referencing Observations

When citing an observation by number — in conversation, in a review report,
or from within another observation — the number must come from the entry's
literal `### Observation N:` header line. Never cite an observation number
that wasn't read from that header.

- **Search-tool line numbers are positional metadata, not IDs.** `grep -n`
  prefixes every match with a line number; when a match lands mid-entry
  (e.g., on a Session context or Principle line rather than the header),
  that line number is NOT the observation number. Resolve to the owning
  header first — scan backwards from the matched line to the nearest
  preceding `### Observation N:` header and take the number from there
  (e.g., an awk backwards-scan, or re-grep for `^### Observation` and pick
  the last header line before the match).
- **Plausibility check (cheap second layer):** before quoting any
  observation number, compare it against the known counter range — the
  highest `### Observation N:` header in the log. A number outside that
  range (e.g., citing #1365 when the log's counter is at #766) is almost
  certainly a line number or other positional artefact misread as an ID.

The general rule: IDs must come from the record's own identifier field,
never from the positional metadata of the search tool that found it.

## Taxonomy (quick version)

**Open-source** — client-agnostic, methodology-driven, useful to other
practitioners. **Internal** — contains user/client/project specifics or
personal preferences. Default to open-source when it could go either way,
stripping specifics. The boundary is also a confidentiality boundary. Full
requirements (attribution, licensing, structure): `references/skill-authoring.md`.

## Archival on Write

On every log write, first move entries that were already ACTIONED or
DECLINED in a *previous* session to
`skill-observations/archive/log-[YYYY-MM-DD].md` (preserving the log header
in the archive). Entries resolved in the *current* session stay in the
active log for one more cycle. The active log keeps its header, status key,
all OPEN entries, and the just-resolved ones.

## Log Structure

```markdown
# Skill Observation Log

Observations captured during task-oriented work.

**Status key:** OPEN = not yet actioned | ACTIONED = skill updated/created |
DECLINED = user decided not to pursue

---

## [Date]

### Observation 1: [Title]
**Status:** OPEN
[... full format ...]
```

## Surfacing Protocol

Default: at end of session, as a grouped summary — improvements grouped by
skill, new-skill candidates listed separately; for each, one sentence plus
suggested type; ask which to act on. Surface earlier when an observation
needs user input to be complete, when a skill is actively producing wrong
output, or when observations cluster on one skill.

**Default to log-and-defer.** Surfacing an observation is not an invitation
to act on it. The default is log-and-defer: state that the observation is
logged for the next review, and stop. Reserve in-session application
strictly for the two triggers already defined under "Acting on
Observations" — an explicit user request that names the action, or
correcting a skill that is producing wrong output in the current session.

Do NOT routinely offer a binary "apply now vs leave for next review" choice
when surfacing observations. For users who run regular reviews, that offer is
unwanted friction repeated every session. If a user has expressed a standing
preference to always defer to the next review, suppress the in-session
"act now?" offer entirely rather than asking each time.

**Self-check before surfacing:** observations were logged throughout the
whole session (including discussion phases); logged silently; each follows
Issue → Improvement → Principle; each is typed; existing-skill items name
the section; no open-source Principle contains client-identifying info;
every appended observation carries a Status line (`**Status:** OPEN` at
write time) — a statusless entry is invisible to any status-filtered review
pass, so if any observation lacks one, add it now. Fix failures before
surfacing.

## Acting on Observations

Act only in three contexts: (1) the comprehensive review (load
`references/weekly-review.md`); (2) an explicit user request ("update X
skill", "act on observation #N"); (3) in-session correction when a skill is
producing wrong output the user should know about. Otherwise: log, don't
act.

When acting: small, clearly-additive, low-risk changes (a new rule, a
clarification, a factual fix) may be applied directly. Substantial changes
(restructuring, new capabilities, changed methodology) and all new-skill
creation: load `references/skill-authoring.md` first and follow its editing
and staging rules. If an observation reveals a principle that applies to
skills generally, propose it for the cross-cutting principles file (see the
same reference).

## Quick Reference

| Question | Answer |
|----------|--------|
| When do I observe? | The whole session, including feedback and reflection phases |
| How do I log? | Silently, immediately, appended to the end, with the 3-step numbering discipline |
| When do I surface? | End of session, or earlier if needed |
| Status line? | Mandatory `**Status:** OPEN` as the first field of every new observation; reviews treat statusless entries as OPEN, never as nonexistent |
| Citing an observation number? | Only from its literal `### Observation N:` header — `grep -n` line numbers are positional metadata, not IDs; sanity-check against the known counter range |
| Open-source or internal? | Default open-source; the boundary is confidential |
| Small fix or substantial? | Additive → apply directly; restructuring/new skill → `references/skill-authoring.md` |
| Weekly review? | Trigger check at session start; procedure in `references/weekly-review.md` |
| No filesystem? | Handoff-doc mode — `references/environments.md` |
