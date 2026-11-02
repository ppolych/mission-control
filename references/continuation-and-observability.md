# Continuation, observability, and selective memory

## Contents

- [Progress, verified waits, and no progress](#progress-verified-waits-and-no-progress)
- [Automatic metrics from committed state](#automatic-metrics-from-committed-state)
- [Handoff for another session or agent](#handoff-for-another-session-or-agent)
- [Search lessons selectively](#search-lessons-selectively)
- [Bounded recovery from transient observations](#bounded-recovery-from-transient-observations)
- [Origin and adaptation](#origin-and-adaptation)

These additions were introduced in 0.3.1 and remain available in 0.4.2.7. Contract schemas,
approval policy, attempt budgets and recovery transitions are unchanged. All
three helpers below are read-only: they do not execute checks, add journal events,
record approvals, or reset counters. Explicit shell redirection writes an export.

## Progress, verified waits, and no progress

After a substantial agent turn, classify it with evidence:

- **Progress**: authoritative state changed, a requirement completed, or new
  evidence materially changes the next action. Reworded plans and status messages
  alone are not progress. A successful irrelevant command is not goal progress.
- **Verified wait**: a specific process/session/job handle is currently confirmed
  live by its owning tool/system. Record the handle, observed status, observation
  time, and next bounded poll. A lock file or an old log does not prove liveness.
- **No progress**: neither meaningful advancement nor a verified live wait.
  Diagnose the blocker, inspect alternatives, and take the next authorized action.

An observation timeout or transient polling failure is not proof that execution
failed. Poll the same handle or inspect authoritative external state before any
restart. A terminal or missing handle requires inspection/recovery, not a blind
rerun. Handle/PID reuse must be considered; prefer the owning tool's job identity.
Waiting for a user approval remains `awaiting_approval` (exit 3), not a process
wait or permission to self-approve. Never consume execution attempts just to poll.

Record concise observations in the decision log using `templates/progress-note.md`.
This is an agent classification, not a process monitor or scheduler. Existing
CLI failure thresholds, including `no_progress`, retain their original meaning;
do not import another runtime's numeric thresholds or hide failures as waits.

## Automatic metrics from committed state

```bash
python3 "$SKILL/scripts/mission.py" metrics --mission "$mission"
```

Produces one JSON line suitable for an explicit `metrics.jsonl` export. Journal
validation happens first. `attempts_used` and `revalidations` come from counters;
`event_counts` counts committed actions; `terminal_transitions` records changes
of nonempty stop reason rather than repeated observations. `exit_id` is the
journal-head hash (schema 3), or a checkpoint digest (schema 2). Repeated reads
of the same checkpoint yield the same ID and no new events. Deduplicate stored
exports by that ID; cumulative snapshots must not be summed across resumes.

`duration_seconds` is elapsed time between first journal event and checkpoint
update, including pauses, not active execution time. It is null when unavailable.
Schema-2 event counts are null because no journal exists. Token use and human
interventions stay null: recorded approve/deny counts do not prove how many
human interactions occurred, and host token accounting is not available here.

Export final metrics AFTER goal review. A `finish` transition may record
step-level `done_verified`; `goal_review_passed` reports the stored judgment,
not fresh semantic/coverage proof. Use `coverage` and inspect current artifacts
before claiming success. Terminal transition counts are history, not distinct
missions or evidence of final goal satisfaction. An active snapshot has a null
exit label. `templates/metrics-entry.json` documents the export shape.

## Handoff for another session or agent

```bash
python3 "$SKILL/scripts/mission.py" handoff --mission "$mission"
```

Returns structured JSON with the original goal, constraints, pinned workspace,
contract hash, checkpoint/journal pointers, step statuses, dependencies, active
steps, recovery flags, pending requests, stored approval digests and check refs.
Save it explicitly as `handoff.json` if useful. It does not replace the checkpoint
or grant approval. It intentionally omits command output and manual rationales;
pending request snapshots still contain the declared commands and criteria.
Keep secrets out of those definitions.

On resume, re-read current state, inspect the workspace, and use recovery for
uncertain work. Stored digests and statuses in a handoff are historical hints;
current approval identity and evidence freshness are enforced by the lifecycle.
The exporter itself does not assert that the workspace or approvals remain live.

## Search lessons selectively

```bash
python3 "$SKILL/scripts/mission.py" lessons-search \
  --lessons-root /known/mission-history --query deployment --limit 5
```

Follow next_offset if present:

```bash
python3 "$SKILL/scripts/mission.py" lessons-search \
  --lessons-root /known/mission-history --query deployment --limit 5 --offset 5
```

This helper works before initialization; default scope is `--mission` directory.
Specify an existing known store, not a global filesystem search. Repeated queries
must all match a line, case-insensitively. Results contain relative paths, source
line numbers and snippets capped at 500 characters; read relevant surrounding
source before applying a lesson. History is not proof of current behavior.

Traversal is deterministic, skips hidden entries and symlinks, and examines at
most 64 directories and 32 Markdown files, with a 64 KiB regular-file limit.
Reads are no-follow and nonblocking. Offset range is 0..1000 and page size 1..50.
A next offset covers matches within the scan, not an unlimited filesystem cursor.
A truncated scan requires a narrower root/query, not a claim that no lesson exists.
Unsupported, oversized or unreadable files are skipped; this is selective
retrieval, not an exhaustive audit or a sandbox. Do not place secrets in lessons.

## Bounded recovery from transient observations

Classify before retrying: invalid input, denied permissions, unmet requirements,
and ambiguous external execution are not transient connection failures. For a
confirmed transient read/poll error, keep the same live handle, honor any server
Retry-After advice, and use a bounded delay (for example 1, 2, 4 seconds, at most
three observations) within the remaining host/time limits. If observation still
fails, report the uncertainty and use the existing recovery/stop policy.

Do not retry deploys, writes, messages, payments or arbitrary failed verification
commands through this rule. An execution timeout is not "not applied". Schema-3
`retry: inspect` still needs a current report-bound recovery decision; `safe`
remains the author's constrained safety assertion. There are no implicit CLI
retries, transport switches, or budget resets in this release. Optional advisory
service circuit helpers are documented in reliability patterns (`references/reliability-patterns.md`).

## Origin and adaptation

Adapted from the locally reviewed Codex goal continuation prompt, goal metrics,
selective memory retrieval, compaction handoff prompt and retry handling. Only
workflow patterns are reused; no Rust runtime or multi-agent execution is added.
For actionable bug-review standards, see `review-quality.md`.
