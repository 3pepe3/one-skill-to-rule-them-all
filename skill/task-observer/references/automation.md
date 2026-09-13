# Opt-in lifecycle application

Only an explicit user request may enable state-root `automation.json` with
`enabled: true` and `mode: "root-review-and-install"`. Record its authority and
scope there. This authorizes review, staging, validation and installation within
that scope without asking again. It does not authorize external publication,
provider calls, background model processes, development subagents or editing
refreshable plugin caches. Use a durable user-owned companion for plugin guidance.

The normal review and complete-copy staging workflow still applies. Classify
scope before choosing a target: global skills receive only portable workflow
improvements; project-specific changes go to that project's canonical `.codex/`
or other instructed owner. Central storage does not make a record global.
Read every
record body, verify current target content, classify already-satisfied guidance,
and apply only supported improvements. Keep conflicting, unsupported or unsafe
items open with an explanation. Do not paste records blindly into instructions.
Before installation, verify the live base still matches captured fingerprints,
retain a recoverable backup, atomically replace the owned files and verify the
installed content. Record each target disposition and remove only its completed
pending manifest entry. Current read-only or explicit user constraints prevail.

`Stop` calls `lifecycle`, which requests one continuation in the existing root
thread per pending-record fingerprint and session. It avoids recursive stop-hook
turns. Failed or deferred records remain intact; they do not become actioned merely
because a review was requested. On startup, resume, clear or compact, the existing
SessionStart hook exposes pending work and the applicable opt-in authority.

`SessionEnd` calls `lifecycle` synchronously with a maximum three-second timeout.
It only saves a sanitized pending-review marker; it cannot do semantic review or
start a model turn after exit. Normal pre-exit application happens through Stop.
Abrupt shutdown or clearing before review finishes leaves records for the next
root thread. A busy state lock causes a fast no-op; records remain the authority.

Disable automation by setting `enabled` to false. No recurring service or separate
agent is installed. `PreCompact` checkpoints pending work for manual and automatic
compaction without blocking it or marking records applied. It uses the same
sanitized marker and nonblocking lock as exit. The existing
`SessionStart(compact)` activation requests review after compaction. Read-only
contexts remain non-mutating when supplied in the hook input or CLI options.
No transcript is read by the checkpoint.

Observe real hook execution after restarting Codex; fixture
tests alone do not prove that a running client has reloaded its hooks.

Protocol reference: [Codex hooks](https://learn.chatgpt.com/docs/hooks).
