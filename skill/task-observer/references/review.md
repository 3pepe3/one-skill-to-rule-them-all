# Authoritative review workflow

Read this when the user asks for a task-observer review or accepts the stale
review offer. A single Codex agent can complete every step; collaboration is an
optional apply-phase optimization only.

## Permission gate

An explicit recorded `root-review-and-install` automation authorization follows
`references/automation.md` and replaces repeated interactive approval within its
scope. Read-only restrictions, complete staging, validation and drift checks still
apply. Without that authorization, use the interactive gates below.

In plan mode, a read-only sandbox, or a review-only request, perform a
frontmatter scan and report what a mutable review would do. Do not initialize,
archive, unpark, edit statuses, write the review date, stage updates, or create
empty checkpoints. State the deferred actions explicitly.

In an interactive mutable review, classify and read before asking for approval.
The order is `scan -> read bodies -> cluster decisions -> present counts -> ask`.
A declined or dismissed approval prompt is not approval. Only an explicit yes
to identified items authorizes staged changes; it never authorizes replacement
of live skills.

## Complete single-agent workflow

1. **Load and reconcile.** Run `archive`, then `scan`. Enumerate every active
   file and require `files == parsed + malformed`. Treat missing, blank, or
   unknown statuses as open. Parked records are visible but outside the work
   queue. Re-check each `parked_until` condition; only a condition proven met
   permits returning it to open.
2. **Short-circuit honestly.** Read active cross-cutting principles. If there
   are no open records and no outstanding principle, report that fact, write
   today's review date, and stop. Do not offer recurring setup on an unused
   installation.
3. **Classify scope and inventory durable targets.** Determine whether the
   improvement is portable across projects or depends on this project's product,
   release stage, architecture, policy or toolchain. Project-specific guidance
   belongs in the canonical project owner, typically its `.codex/` rules,
   instructions or skills, following its bootstrap. Verify already-covered rules
   instead of duplicating them. Do not insert project policy into a global skill,
   even as a conditional rule. Application bugs stay in application code.
   Confidentiality (`internal` or `open-source`) is separate from target scope.
   A record's current skill tag or central storage location is only a routing
   hint, not the destination. Record the selected scope and exact owning paths
   in its resolution. For portable improvements, resolve installed skills through Codex's live
   skill surface and paths. Classify each target as user-owned and durable,
   refreshable/volatile, or unavailable/read-only. Never edit any category in
   place. A volatile or unavailable target needs a durable user-owned companion
   or a Codex instruction change within the applicable user authority. A generic
   home companion must not embed one project's contracts.
4. **Read and cluster.** Read every open record body before disposition. Group
   records by the decision they require, not merely the title or filed skill.
   Consolidate proposed skills by problem. Mark an earlier record superseded
   only when a later body's evidence actually invalidates its mitigation.
5. **Propagate.** Evaluate each open Principle against all installed skills and
   active cross-cutting principles. Re-do missing sibling checks and widen
   targets when required. A multi-skill record remains open until every listed
   target is applied, declined, or otherwise recorded in its resolution.
6. **Check confidentiality.** Remove unnecessary identifying details from the
   Issue and Suggested improvement of every open-source record before it is
   used as shareable source material. Its Principle must already be fully
   generic.
7. **Present decisions.** Show grouped IDs, titles, one-sentence evidence-led
   summaries, real per-cluster counts, proposed targets, and judgment calls.
   Wait for blanket or selective approval before staging interactive changes.
8. **Stage approved updates.** Follow `references/skill-updates.md`. Copy the
   complete live directory to the dated state-root staging path, prove the copy
   starts identical, integrate approved observations coherently, and validate.
   Existing same-day staged work is merged or reported as a conflict, never
   overwritten by modification time.
9. **Bookkeep centrally.** After staged validation, update only the permitted
   frontmatter fields in each applied record: `status: actioned`, today's
   `resolved`, and a `resolution` naming every target disposition and staged
   path. Do not archive same-day records. Write today's date to
   `last-review-date.txt` only after the review actually ran.
10. **Report.** Summarize staged skills, actioned IDs, family coherence,
    still-parked records and their conditions, skipped/manual decisions,
    malformed records, and the exact live-install approval still required.

## Optional collaboration branch

Use collaboration only when its tools appear in the live surface and the apply
phase spans more than roughly three skills or ten observations. Do not enable a
persistent feature flag. Partition by skill with explicit observation-ID
ownership. Collaborators may read assigned bodies and edit separate staged
directories; they do not change observation status, review dates, manifests, or
live skills.

The parent owns the final merge and verifies cross-slice duplicates, vocabulary,
all expected totals, complete multi-skill propagation, and every finding that
will be reported to the user. Sequential execution remains the fallback and the
reference behavior.

## Opt-in backfill and recurring review

A first-run history backfill is offered only when the initialized log is empty
and durable project history exists. Ask before reading broadly or writing. Each
accepted candidate is logged through the normal atomic command, cites its
durable source in `session_context` or `reference`, and receives a real sibling
check. Never infer a user's approval from the existence of history.

Recurring review setup is also opt-in. Verify that its execution environment can
reach this local state before offering it. If it cannot, suggest a calendar
reminder for a local manual review. Do not create external tasks, services, or
provider calls without separate authorization. A failed registration never
writes a success marker.
