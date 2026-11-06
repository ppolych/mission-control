# Commands: lifecycle and contract

## Contents

- [Command list](#command-list)
- [Contract format](#contract-format)
- [Checkpoint and wrappers](#checkpoint-and-wrappers)
- [Start validation, assessments, and workspace](#start-validation-assessments-and-workspace)
- [File and absence checks](#file-and-absence-checks)
- [Initialization without overwrite](#initialization-without-overwrite)
- [Process outcome evidence](#process-outcome-evidence)
- [Input and recovery validation](#input-and-recovery-validation)
- [Contract selection and retained judgments](#contract-selection-and-retained-judgments)
- [Drafting, final goal review, and learning records](#drafting-final-goal-review-and-learning-records)

The command list, contract format, checks, initialization, goal review and migration.

## Strict commands

`red --step STEP`, `test-first-note --step STEP --reason TEXT`, `verify --already-satisfied --rationale TEXT` and
`scope-note --path P --disposition D --rationale TEXT` apply to contracts with `discipline: strict`. Their rules
are in the strict discipline reference.

## Command list

Run `python3 "$SKILL/scripts/mission.py" COMMAND --mission PATH`. `--help` lists every command and flag.

- `validate --contract FILE`: validate schema-2/3 JSON without executing checks.
- `init --contract FILE [--workspace PATH]`: initialize a mission without replacing existing state.
- `status`: print checkpoint JSON.
- `coverage`: show schema-3 requirement mappings and current/stale verdicts.
- `criterion-review --criterion ID --verdict supported|unmet|unverified --rationale TEXT [--evidence-ref REF ...]`: record an evidence-linked acceptance judgment.
- `recovery --step ID`: show current schema-3 recovery evidence and report digest.
- `recover --step ID --digest HASH --resolution completed|not_applied|applied_incorrect|partial|unknown --rationale TEXT`: reconcile uncertain effects without executing or refunding attempts.
- `revision-diff --contract FILE`: compare the proposed contract with the stored parent without mutation.
- `revise --contract FILE --destination NEW_PATH --reason TEXT`: publish a separate linked schema-3 revision; parent state and approvals stay unchanged.
- `history`: print schema-3 committed transition events; legacy schema 2 yields an empty list.
- `start --step ID [--context TEXT] [--revalidate]`: begin an attempt with dependencies complete; controlled gates return 3 before reserving an attempt. In schema 3, `--revalidate` also reopens one completed step whose receipt is stale, for checks only; other steps stay completed, and a current step refuses it. On a `done_verified` mission it reopens the mission for that step alone, archiving the goal review; `finish` and `goal-review` are then needed again.
- `approve|deny --step ID --digest HASH --rationale TEXT`: record an explicit user decision for the current presented controlled-mode request.
- `assess --step ID --check INDEX --verdict pass|fail|unverified --rationale TEXT`: record a manual check judgment; indexes start at zero. Unverified leaves checks waiting, not failed.
- `verify --step ID`: execute checks and save evidence; exit 1 means failure.
- `block --step ID --reason TEXT`: park the active step with a nonblank diagnosis.
- `stop --reason LABEL`: record a non-success stop reason.
- `resume`: invalidate completion, preserve counters, and allow revalidation.
- `finish`: require every step completed and set step-level `done_verified`.
- `goal-review --verdict pass|fail --rationale TEXT`: record the post-finish holistic goal assessment; failure sets `blocked` without invalidating step evidence.
- `migrate --destination NEW_PATH`: convert an unversioned legacy mission into a separate directory; initialize the new mission afterward.

## Contract format

A contract has `schema_version` 2 or 3, a mission description, optional mode/constraints/budget,
and nonempty `steps`. Each step has a unique nonempty string `id`, optional
string description, optional `depends_on` string array (default empty), and
nonempty `verify` array. Budget accepts only `max_attempts_per_step`,
`max_iterations`, and `no_progress_threshold`, each a positive integer.
Constraints, if present, are a string array. Mode is `autonomous` (default) or `controlled`; risk is `low` (default),
`medium`, or `high`; needs_approval is a strict boolean (default false).
Gated controlled steps must declare a nonblank description and `commands`: an
array of exact nonempty command argv arrays, or `[]` for no work commands.
Invalid recognized mode/risk/boolean/commands values are rejected by both validate and init.
Manual objects contain only `manual`; argv checks must use a supported type
and valid arity. `exit0` requires a nonempty executable; `test` requires an
expression. Shell/regex semantics are checked at execution, not by running
commands during validation. Each check is either an argv
array such as `["file", "report.txt"]` or `{"manual": "Assess accuracy"}`.

## Checkpoint and wrappers

The checkpoint `state/progress.json` contains status, attempts, evidence,
manual judgments, failure counts, timestamps and stop reason. A contract hash
prevents accidental requirement changes. A nonblocking Unix lock serializes mutating
CLI operations; reports read without it. Checkpoints use same-directory atomic replacement. JSON is the
canonical evidence record; `status` supplies the readable summary.

Shell wrappers retain `file`, `not_file`, `exit0`, `exec`, `test`, and `grep`.
In the standalone wrapper, separate checks with `--`. To pass literal `--`
arguments, use `verify.sh --single TYPE ARGS...`: every token after `--single`
belongs to one exact check, with no separator parsing. For example:
`verify.sh --single exit0 printf '%s\n' -- hello`. Single mode cannot chain
checks; invoke the wrapper separately or use contract checks for multiple arrays.
JSON contract checks always preserve each array exactly, including literal `--`;
they never use the wrapper's separator parser. `exec` accepts one trusted Bash string and enables
pipefail. `VERIFY_TIMEOUT` defaults to 60 seconds. Exit codes: 0 success,
1 negative check/repeat, 2 invalid input or execution error. Standalone wrapper commands execute in the caller's current directory.
Lifecycle checks execute in the mission's pinned workspace. Paths containing spaces remain single arguments.

Legacy repeat commands: `record TOOL ARGS...`, `check TOOL ARGS...`, `history`,
`reset`. `NO_PROGRESS_STATE` selects the JSON history file and
`NO_PROGRESS_THRESHOLD` defaults to 2. Parallel records wait briefly on a lock next to the history file, so none are lost. History contains hashes rather than
arguments; legacy text histories must be reset or replaced. These compatibility
commands count calls, not failures; the lifecycle CLI tracks verification failures
per step and context.

Migration supports legacy `features`/`steps` and `steps`/`verify`. It preserves
original JSON in `legacy/`, retains legacy completion as historical metadata,
and converts textual checks to manual criteria. Review these before initializing;
no legacy text is automatically executed. Migration does not copy external artifacts.

## Start validation, assessments, and workspace

Start checks status, single-active-step and dependencies before budget limits.
An invalid transition returns 2 without writing the checkpoint or stopping an
active mission. A valid start exceeding the whole-mission iteration cap records `max_iterations`.
A denied per-step retry marks that step `budget_exhausted: true`, returns 1, and
records mission-wide `budget_exhausted` only if no useful ready work remains.

Missing manual assessments are incomplete input, not a failed criterion. Verify
preflights their presence before running any deterministic commands, returns 2,
and leaves state unchanged. Assess the still-active attempt, then verify again;
no attempt is refunded or added. An explicit `fail` verdict is a real failure:
verification runs deterministic-first, records the failure and ends the attempt.

Initialization pins an absolute, resolved workspace: `--workspace PATH`, defaulting
to the initialization caller's current directory. All lifecycle file checks and
subprocesses use that directory; evidence records it. Later caller directories
cannot change verification semantics. There are no per-check directory overrides.
A missing workspace returns 2 without changing state. Commands may themselves
change directories, and absolute check paths remain absolute.

Older checkpoints without a workspace must use `resume --workspace PATH` once;
this invalidates completion and pins the selected directory without resetting
budgets. An already pinned workspace cannot be overridden. Inspect legacy evidence
to select the correct workspace before resuming. Standalone `verify.sh` remains
caller-relative because it does not load a mission.

## File and absence checks

`file PATH` follows symlinks and passes when a target exists (including a
directory); it is not a regular-file type check. `not_file PATH` means no directory
entry at PATH: regular files, directories, valid symlinks and dangling symlinks
all fail it. It uses `lstat` without following the final symlink. A missing entry
or nonexistent parent passes; permission and other inspection errors are errors,
not evidence of absence. Use `test` with an explicit expression for other type
or target-access requirements. Relative paths use the pinned workspace in
lifecycle checks and the caller directory in standalone checks. These are
point-in-time filesystem checks and do not prevent concurrent filesystem changes.

## Initialization without overwrite

If `contract.json` already exists, init compares parsed JSON with the supplied
contract. Different content is an error; neither contract nor existing checkpoint
is modified. Identical content is accepted without rewriting its original bytes,
including `init` reading the destination itself (or omitting `--contract`).
Destination contract symlinks are rejected rather than replaced. Invalid existing
JSON is an error, not permission to overwrite it.

Contract and checkpoint writes are individually atomic, not one transaction.
An interruption after contract creation can leave a contract-only mission. Retry
init with the same contract and the intended workspace; init writes only the
missing checkpoint. Workspace is pinned when that checkpoint is created. Any
existing checkpoint, including an unreadable one, prevents initialization from
resetting state; inspect or recover it explicitly.

## Process outcome evidence

`code` is the normalized check result: 0 pass, 1 negative result, 2 execution
error. It is separate from `command_exit_status`: the actual subprocess return
code (for example 2 for `exec "exit 2"`). A process killed directly by a signal
has a negative return code, a positive `signal` number and `error_type: signal`.
Shell-translated signal statuses, such as 143, remain ordinary positive statuses;
the controller does not infer an underlying signal from them.

A timeout records code 2, `error_type: timeout`, and null exit status/signal
because no normal return status was obtained. Start/inspection errors record
code 2 and only their exception class (for example `FileNotFoundError`), with
null exit status/signal. No exception message or subprocess output is retained.
Manual and filesystem checks have null process status and signal. A grep syntax
or I/O error retains its process status with `error_type: grep_error`. Malformed
`test` expressions likewise retain status 2 with code 2 and `error_type: test_error`;
a valid false expression remains code 1.
Lifecycle `verify` returns 1 for any recorded unsuccessful check, while wrapper
execution errors return 2. Input/preflight errors return 2 without consuming an
additional attempt. Check definitions and manual rationale remain verbatim;
these fields must not contain secrets.

## Input and recovery validation

Command argv strings cannot contain NUL bytes. The `file`, `not_file`, and `grep`
filesystem path arguments cannot be empty; an empty string is never shorthand
for the workspace directory. Assessments require nonblank
rationale. Checkpoint structure, step identifiers/statuses, counters, mappings,
stored evidence, history and observation records, and the single-active-step invariant are validated before every command;
malformed state returns an input error without repairing or resetting it.
Preserve the file and inspect it before explicit recovery. Pending controlled requests validate the complete stored step, request status,
workspace, revalidation boolean and matching digest; malformed requests are
rejected without being silently regenerated. Structural validation
is not evidence authenticity or protection against deliberate state edits.

Migration parses legacy inputs and backup JSON before writing the destination.
Malformed inputs leave no new destination; ambiguous simultaneous legacy step
collections are rejected. Migration writes the complete contract and backups into
a reserved sibling staging directory, then publishes them with a directory rename.
A write or publication failure leaves the destination absent and cleans up staging
on normal exception handling, allowing retry. After an abrupt exit, rerun the same
migration with the same destination: a destination-specific lock permits safe
removal and rebuilding of stale staging. A still-running migration causes an
input error without touching its staging. Source files are never modified.

The reserved sibling paths are `.mission-migration-<destination-hash>.stage` and
`.mission-migration-<destination-hash>.lock`. Do not store user files there. The
lock file intentionally persists to preserve the shared lock inode; it is not a
failed migration. Symlink or nondirectory staging entries are refused. Unrelated
directories, including random staging left by older versions, are not removed.
A crash still stops the process; recovery occurs on the next invocation. This is
a cooperative local workflow, not a guarantee against hardware failure, filesystem
corruption, or arbitrary concurrent external filesystem edits.

## Contract selection and retained judgments

`--contract` is accepted by `init`, `validate`, `revision-diff` and `revise`.
Revision commands load the stored parent first and use the supplied file only
as a proposal. Execution lifecycle commands
load the destination mission contract and compare it to the checkpoint hash;
an external contract cannot bypass a changed stored contract. Contract dependency
validation uses an iterative traversal, including for long chains.

Starting another attempt archives existing manual judgments and evidence, then
clears both. A retry requires fresh assessments, while prior rationale
remains available in history. Legacy migration requires each step's criteria to
be a nonempty array of nonblank strings; bare strings and simultaneous `steps`
and `verify` criteria are rejected rather than guessed or split into characters.

JSON input files are decoded as UTF-8 with optional BOM, independent of process
locale. Both CRLF and LF are accepted. Generated JSON uses UTF-8 without BOM and
LF newlines. This applies to contracts, checkpoints, migration backups and repeat
history. UTF-16 inputs require conversion before use.

## Drafting, final goal review, and learning records

Use `templates/draft-contract.md` to self-answer the five drafting questions.
There is no `plan` subcommand: the structured template is the lightweight planning
interface. Inspect workspace and relevant past lessons first; present a complete
draft rather than asking the user to construct it. Existing authorization governs
execution, not the number of steps. See agent workflow (`references/agentic-workflow.md`).

`goal-review` is an additive command available only after successful `finish`
with all steps completed. It requires an explicit pass/fail verdict and nonblank
rationale, and stores `goal_review` with verdict, rationale, timestamp, goal and
contract hash. Return codes: 0 pass, 1 unmet/uncertain goal, 2 invalid transition
or missing input. It does not run commands, increment attempts, or change step
evidence. The rationale should cite actual artifact/check results and compare
them with the original user request, not just assert that the steps passed.

A fail changes the stop reason to `blocked`. Neither finish nor a later review
can override that stop: use the existing recovery/revision policy. A repeated
review while still `done_verified` archives the previous review, allowing a later
inspection to discover a gap. `resume` archives and removes the current review
and invalidates completion normally. Goal review cannot override `human_abort`,
`human_paused`, budget exhaustion or other stopped states.

Compatibility: existing contracts need no migration and `finish` retains its
step-level behavior. The agent-facing skill requires the post-finish review
before reporting success; old CLI callers are not forced into a new workflow.
This is a recorded human/agent assessment, not automatic semantic verification.
Contract-time holistic criteria or an ordinary final `goal-check` step supplement
it using existing `assess` and `verify` commands.

The agent, not the CLI, writes `.mission/lessons.md` (at most two lessons per
mission), the non-done retro in `.mission/decision-log.md`, and explicit exports from `metrics`
in `.mission/metrics.jsonl` (requested by this skill workflow). Templates supply
formats; these artifacts never mutate the frozen contract or reset budgets.
Metrics use actual final exit labels and cumulative execution attempts; human
interventions are null when unknown. Exit IDs prevent duplicate snapshots.
Resumed exits are one mission for five-mission learning reviews. Skill-level
promotions and version policy are in skill learnings (`references/skill-learnings.md`).

### Contract strictness and timeouts

`validate`, `init --contract`, `revise` and `revision-diff` return 2 on unknown top-level
or step fields, naming them; fields starting with `_` are comments. Frozen contracts are
not rechecked. Step `verify_timeout` takes 0 < seconds <= 86400 and overrides
`VERIFY_TIMEOUT`. `verify` prints `PASS|FAIL: KIND (check N, exit S)`, with a signal,
`timeout after Ns` or error type in place of the exit status; check output stays discarded.
