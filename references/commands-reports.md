# Commands: reports

Read-only commands and how to interpret them.

## Operational reports

`metrics --mission PATH` emits one JSON line derived from validated checkpoint and
journal. It does not write metrics.jsonl automatically. Use its exit_id to deduplicate
explicit exports, and export after final goal review. Unknown usage/interventions
are null; schema-2 journal counts are unavailable rather than invented.

`handoff --mission PATH` returns structured current goal, status, approval and
evidence pointers without changing state. It is historical context, not authority
to execute or proof that approvals/evidence remain current.

`lessons-search --lessons-root PATH --query TEXT [--limit 10] [--offset 0]`
works without initialization. It searches a known bounded Markdown store, skips
symlinks and unsupported files, and returns path/line references plus next_offset.
Files it could not read, such as those over 64 KiB, appear in `skipped_files` and set `truncated`.
Repeat --query for AND matching per line. Unknown/missing store or invalid bounds
return 2. Read the detailed semantics (`references/continuation-and-observability.md`) before
using exports or interpreting an incomplete scan as an absence of lessons.

The guidance for progress classification, safe bounded polling and retries does
not add an implicit execution retry or alter inspect/approval/budget rules.

## Evidence and diagnosis reports

- `evidence-audit`: read-only schema-3 sufficiency gaps; return 0 means report
  generation. Inspect all_sufficient and criteria.
- `criterion-review ... --evidence-kind KIND` (repeatable): required when an
  acceptance item opts into evidence_kinds. Kinds: existence/content/behavior/
  integration/manual. Labels require real inspection; they are not proof.
- `diagnose`: recorded-fact failure classes and recovery-first next checks.
- `lesson-audit --record FILE [--as-of ISO]`: advisory validity/age/contradictions.

## Continuation hints and installation identity

`handoff` and `diagnose` now add `installation` (version, absolute CLI path and fresh engine fingerprint) and `mission_directory`. Each step adds `missing_assessments`, `unverified_assessments`, `blocked_dependencies`, `suggested_action` and `retry_authorized: false`. Assessment indices are zero-based check positions. These read-only reports spend no attempts, append no journal events and do not detect the host UI's agent/plan mode.

Suggested actions prioritize user denial, mission stops, uncertain-outcome recovery and pending approval. Active steps suggest completing assessments or verification; pending work reports dependencies, other active work, revalidation and budget boundaries. All suggestions require current evidence and independent lifecycle/host permission checks; they never authorize retry or automatically resume a stopped mission.

Prefix resolution is reused only within one allowed-path validation call. Each later validation resolves again. Approval/evidence checks and postflight cache bindings remain fresh.

## Structural traceability in evidence-audit

The read-only schema-3 `evidence-audit` report includes `traceability.criteria`.
Each item contains the acceptance `id`, its contributing `steps` (each with `id`,
`checks` containing zero-based `index` and `kind`, and declared `outputs`) and
`relationship: declared_step_mapping`. Command arguments and output content are
not added to this structural report.

`traceability.unmapped_steps` lists support work without acceptance_refs. It is
informational and does not reject valid contracts. `traceability.behavior_proven`
is always false: this section describes declarations, not execution or semantic
coverage. The existing coverage/sufficiency fields remain separate and unchanged.
A step mapped to several criteria exposes the same shared checks for each;
reviewers must assess which checks actually establish each outcome.

Inspect this map before execution alongside the drafted scenarios. Use the
execution-context workflow (`references/execution-context.md`) for a selected mission's brief,
decision log and combined-outcome review. No new command, schema field, authority,
attempt consumption or lifecycle transition is introduced.

## Compact handoff and structural indexing

`handoff --compact` is an optional read-only projection. It includes installation
identity, selected root/workspace/contract, stop reason, active step, status counts,
at most five step rows, next_ready_step, omitted_steps and pending_approval_count.
A ready identifier is advisory, not an approval or retry grant. Use plain handoff
for the complete report. `--compact` on any other subcommand is rejected before
checkpoint mutation.

Active-work status is collected once per report. Acceptance-to-step indexes are
local to each call and shared by coverage/traceability in evidence-audit. They
store structural relationships only, not file hashes or mutable authorization.
Existing fresh observations and receipt checks remain unchanged.

## Report behavior

Reports (`status`, `history`, `metrics`, `handoff`, `coverage`, `recovery`, `diagnose`,
`evidence-audit`, `revision-diff`) read the atomically replaced checkpoint without taking
the mission lock, and refuse a non-regular `.lock` entry. Other commands report a busy lock
by name with exit 2. Only `init` creates a mission directory. `status`, `handoff` and
`diagnose` include `goal_review_status`: `missing`, `pass`, `fail` or `not_applicable`.
`resume` accepts `--rationale`, required from `human_abort`, recorded in `resume_history`.
