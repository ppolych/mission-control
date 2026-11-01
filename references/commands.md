# Commands and state

Mission Control 0.3.3: `python3 scripts/mission.py --version` (also supported by
both shell wrappers). The canonical release number is in `VERSION`; the contract
new-contract schema is 3; schema 2 remains supported. For WSL2 prerequisites and paths, see [WSL setup](wsl.md).

For schema-3 acceptance mappings, supported/unmet/unverified reviews, watched
inputs, declared effects, recovery, linked revisions and the atomic journal,
read [evidence and recovery](evidence-recovery.md). These are opt-in through a
new schema-3 contract; schema-2 missions retain their existing execution rules.

## Controlled-mode approval policy

Version 0.2 adds an opt-in mission-level `mode`. Omitted mode is `autonomous`;
its execution transitions, budgets, verification, and host authorization remain
unchanged. Use `controlled` for interactive/sensitive work and autonomous for
already sandboxed/CI work. This is an agent coordination policy, not an OS
sandbox, an authenticated approval service, or a grant of host permission.

Each step defaults to `risk: low` and `needs_approval: false`. Allowed risks are
`low`, `medium`, `high`; mode and risk values are case-sensitive. Booleans must
be JSON booleans, not strings, numbers, or null. A controlled step gates when
`risk == high OR needs_approval == true`. Low/medium unmarked steps run normally.
For approval at every step, explicitly set `needs_approval: true` on each one.

Gated steps require a nonblank `description` and explicit `commands`, for example:

```json
{
  "id": "reviewed-change",
  "description": "Update report.txt within the pinned workspace; no network calls",
  "risk": "high",
  "needs_approval": true,
  "commands": [["python3", "scripts/update_report.py", "--", "a b"]],
  "verify": [["file", "report.txt"], {"manual": "Compare the report with the original request"}]
}
```

These command arrays describe work the agent plans to run; the helper NEVER
executes them. Unlike verification checks, they have no `exit0`/`exec` prefix:
the first token is the executable, and tokens are not joined into a shell string.
Explicit shell use must itself be declared as argv, such as `["bash", "-c", TEXT]`.
`commands: []` declares no work commands; the description must still explain
manual/file operations and affected scope. Verification commands and manual
criteria are disclosed separately in the step's existing `verify` array.

1. `start --step ID` validates dependencies, active-work constraints and budgets
   first. If the controlled step lacks matching approval, it stores
   `steps[ID].status: awaiting_approval`, emits a JSON request and returns **3**.
   The request contains the full step, pinned workspace, revalidation flag and
   digest. It runs nothing and spends no execution attempt or mission iteration.
2. Show the exact description/scope, work argv, verification argv/manual criteria,
   workspace and digest to the user. Wait for an explicit decision. Silence,
   elapsed time, a previous mission-level authorization, or the digest itself
   is not consent. Never execute work while awaiting approval.
3. After an explicit approval, run
   `approve --step ID --digest HASH --rationale TEXT`. It records the decision,
   returns 0 and makes the step pending; it does not start the step or run checks.
   Rerun `start` (with `--revalidate` if required), then work/assess/verify.
4. After an explicit refusal, use `deny` with the same digest/rationale arguments.
   It returns 1, removes approval, records the rationale/timestamp/digest as
   `approval_denial`, sets `approval_denied: true` and leaves the step blocked.
   This makes the step unavailable just like an exhausted per-step budget, but
   does not pretend work ran, increment attempts, or add a no-progress failure.
   Existing counters and evidence remain intact. Resume cannot clear this
   denial; recovery requires a new explicitly reviewed mission revision.

`approved_steps` is a checkpoint mapping from step ID to digest, timestamp and
decision rationale. The digest covers the whole frozen contract (including mode,
mission, constraints, descriptions, commands, criteria and risk flags), the step
ID and pinned workspace. IDs alone never authorize work. Approvals remain valid
across retries/resume only while that identity matches. A stale digest requests
approval again; editing a frozen contract remains an error requiring a new
revision. A decision with a stale/missing digest, altered presented snapshot,
blank rationale or no pending request returns 2 without changing the checkpoint.
Schema 3 additionally binds declared watched input observations; input changes
invalidate approval even when the contract text and workspace path are unchanged.
Assessment and verification recheck approval before accepting manual judgments
or running checks. Approval, start, assessment and verification also require the
pinned canonical workspace to remain available and resolve to its stored path;
a missing directory or symlink redirection returns 2 without consuming attempts
or changing checkpoint state. Denial remains possible if the workspace is gone.
This is a preflight identity check, not protection against filesystem races or
replacement by a different directory at the same canonical path.

Waiting is not an active execution attempt, so an independent ready step may
run while another awaits approval. Denied prerequisites never satisfy dependency
checks. When denied work remains and no independent ready/active work remains,
the mission stops `blocked`, rather than falsely reporting completion or
exhausting unrelated budgets. Explicit stops, no-progress and iteration limits
retain their existing precedence. Resume preserves approvals and denials but
discards an unapproved waiting request, which must be presented again on start.

On revalidation, approval still applies to the step's identity, but only the
existing safe acceptance checks may run: do not repeat the declared work commands
or external effects. If more commands become necessary during work, stop and
present a new mission revision before executing them. The helper cannot enforce
what an agent runs between CLI calls, authenticate the user reply, prevent local
checkpoint edits, or substitute for host approval. Never store credentials in
commands, criteria, or decision rationale.

Legacy checkpoints without `approved_steps` are read as an empty mapping; no
migration is required. New checkpoints initialize it to `{}`. Status adds the
`awaiting_approval` step state. Return codes are 0 success, 1 refusal/check failure
or exhausted work, 2 invalid input/transition, and 3 waiting for a controlled step
decision. These codes are coordination signals; no code grants execution rights.

Run `python3 <skill>/scripts/mission.py COMMAND --mission PATH`.

- `validate --contract FILE`: validate schema-2/3 JSON without executing checks.
- `init --contract FILE [--workspace PATH]`: initialize a mission without replacing existing state.
- `status`: print checkpoint JSON.
- `coverage`: show schema-3 requirement mappings and current/stale verdicts.
- `criterion-review --criterion ID --verdict supported|unmet|unverified --rationale TEXT [--evidence-ref REF ...]`: record an evidence-linked acceptance judgment.
- `recovery --step ID`: show current schema-3 recovery evidence and report digest.
- `recover --step ID --digest HASH --resolution completed|not_applied|partial|unknown --rationale TEXT`: reconcile uncertain effects without executing or refunding attempts.
- `revision-diff --contract FILE`: compare the proposed contract with the stored parent without mutation.
- `revise --contract FILE --destination NEW_PATH --reason TEXT`: publish a separate linked schema-3 revision; parent state and approvals stay unchanged.
- `history`: print schema-3 committed transition events; legacy schema 2 yields an empty list.
- `start --step ID [--context TEXT] [--revalidate]`: begin an attempt with dependencies complete; controlled gates return 3 before reserving an attempt.
- `approve|deny --step ID --digest HASH --rationale TEXT`: record an explicit user decision for the current presented controlled-mode request.
- `assess --step ID --check INDEX --verdict pass|fail|unverified --rationale TEXT`: record a manual check judgment; indexes start at zero. Unverified leaves checks waiting, not failed.
- `verify --step ID`: execute checks and save evidence; exit 1 means failure.
- `block --step ID --reason TEXT`: park the active step with a nonblank diagnosis.
- `stop --reason LABEL`: record a non-success stop reason.
- `resume`: invalidate completion, preserve counters, and allow revalidation.
- `finish`: require every step completed and set step-level `done_verified`.
- `goal-review --verdict pass|fail --rationale TEXT`: record the post-finish holistic goal assessment; failure sets `blocked` without invalidating step evidence.
- `migrate --destination NEW_PATH`: convert an unversioned legacy mission into a separate directory; initialize the new mission afterward.

Legacy contract: `schema_version: 2`, mission description, optional mode/constraints/budget,
and nonempty `steps`. Each step has a unique nonempty string `id`, optional
string description, optional `depends_on` string array (default empty), and
nonempty `verify` array. Budget accepts only `max_attempts_per_step`,
`max_iterations`, and `no_progress_threshold`, each a positive integer.
Constraints, if present, are a string array. Mode is `autonomous` (default) or `controlled`; risk is `low` (default),
`medium`, or `high`; needs_approval is a strict boolean (default false).
Gated controlled steps must declare a nonblank description and `commands`: an
array of exact nonempty command argv arrays, or `[]` for no work commands.
Additional metadata is allowed; invalid recognized mode/risk/boolean/commands
values are rejected by both validate and init.
Manual objects contain only `manual`; argv checks must use a supported type
and valid arity. `exit0` requires a nonempty executable; `test` requires an
expression. Shell/regex semantics are checked at execution, not by running
commands during validation. Each check is either an argv
array such as `["file", "report.txt"]` or `{"manual": "Assess accuracy"}`.

The checkpoint `state/progress.json` contains status, attempts, evidence,
manual judgments, failure counts, timestamps and stop reason. A contract hash
prevents accidental requirement changes. A nonblocking Unix lock serializes CLI
operations. Checkpoints use same-directory atomic replacement. JSON is the
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
`NO_PROGRESS_THRESHOLD` defaults to 2. History contains hashes rather than
arguments; legacy text histories must be reset or replaced. These compatibility
commands count calls, not failures; the lifecycle CLI tracks verification failures
per step and context. Do not share compatibility history between concurrent writers.

Migration supports legacy `features`/`steps` and `steps`/`verify`. It preserves
original JSON in `legacy/`, retains legacy completion as historical metadata,
and converts textual checks to manual criteria. Review these before initializing;
no legacy text is automatically executed. Migration does not copy external artifacts.

## Recovery and transition policy

`start` reserves an execution attempt before the agent performs work; interruption
never refunds it. Resume invalidates completion without resetting counters or
failure history. Completed/interrupted steps become eligible for `start
--revalidate`, which consumes no execution attempt and runs only acceptance
checks against existing work. Dependencies must be completed first. After a
failed revalidation, repairs require a normal start within the original budget.
Budget exhaustion requires an explicitly planned new mission revision, not a
counter reset. The helper cannot prevent an agent from performing external
side effects between commands; inspect interrupted actions before any retry.

Only one step may be active, including revalidation. Verify and assess require
an active step. Start, verify, assess and block require an unstopped mission.
`block` permits only `in_progress → blocked` for the active step, including
an active revalidation. It releases the active slot without refunding attempts
or changing other steps' evidence. Pending, completed, and already-blocked steps
reject `block`; it cannot target a different step while work is active. A normally blocked
step may be restarted subject to normal dependencies, remaining budgets, and
revalidation eligibility. A controlled user-denied step is the exception: it
stays blocked for that revision and resume cannot authorize a retry. Use `resume` to reopen completed work: it invalidates
all completion, including downstream steps, before dependency-ordered rechecking.
Rejected block requests leave the checkpoint unchanged.

Stop preserves the active step and existing evidence; it cannot replace an
existing stop reason. Resume clears that active status and records historical
evidence. Finish requires all steps complete and no prior non-success stop
reason; repeated finish on `done_verified` is idempotent, including preserving
the checkpoint timestamp used to identify a reported exit.

Repeated failures count per step, criterion set and caller context. Different
contexts have separate counters; successful verification clears all counters for
the step. Two matching failures stop the mission by default, including failures
during revalidation. Context is user-supplied, not an environment fingerprint;
change it only after relevant prerequisite or tactic changes. Explicit resume
permits recovery but retains history and budgets.

## Evidence and output

Each attempted check records its original index and definition, code, UTC
timestamp, and absolute pinned mission workspace. Deterministic checks run before
manual checks regardless of contract order. The first failure stops evaluation;
checks absent from that evidence list did not run. Failed manual criteria also
stop evaluation. All checks must pass in the same verification run.

Lifecycle verification discards subprocess stdout/stderr instead of buffering or
persisting it. Evidence contains check definitions and manual rationale verbatim:
never embed credentials in either. For diagnostics, run the specific trusted
check interactively with `verify.sh`, which inherits terminal output; review any
output before retaining it. The program cannot guarantee redaction of caller
text or prevent a verification command from creating its own logs or side effects.
Historical evidence is retained, so long-lived missions can grow; archive closed
missions according to workspace policy. Timeout cleanup applies to the verification process group (TERM then KILL);
escaped sessions/external jobs remain outside that boundary. It is not a sandbox.

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

## Per-step exhaustion and remaining work

Execution attempt counters remain authoritative. A denied retry marks the step
exhausted without stopping independent ready steps. Dependencies still require
completed prerequisites. After exhaustion is recorded, each subsequent verify
reassesses whether ready work remains; if none remains and incomplete steps are
budget-limited, the mission stops with `budget_exhausted`. A failed last attempt
can be inspected before requesting another start; exhaustion is classified on
that denied retry. No attempts are refunded. Existing no-progress and explicit
stop reasons take precedence; the whole-mission cap remains mission-wide.

Ready work means an incomplete step whose prerequisites are complete and which
has a remaining execution attempt or is eligible for revalidation. A normally blocked step
with remaining budget can be restarted and counts as available; user-denied
controlled steps are never eligible in that revision; whether its
external blocker has resolved requires operator judgment. If external blockers
prevent further useful work, explicitly stop with `blocked`.

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
and the single-active-step invariant are validated before lifecycle mutations;
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

Starting another attempt archives existing manual judgments with their evidence
before clearing them. A retry requires fresh assessments, while prior rationale
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
execution, not the number of steps. See [agent workflow](agentic-workflow.md).

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
promotions and version policy are in [skill learnings](skill-learnings.md).

## Operational read-only helpers — introduced in 0.3.1

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
Repeat --query for AND matching per line. Unknown/missing store or invalid bounds
return 2. Read [the detailed semantics](continuation-and-observability.md) before
using exports or interpreting an incomplete scan as an absence of lessons.

The guidance for progress classification, safe bounded polling and retries does
not add an implicit execution retry or alter inspect/approval/budget rules.

## Additional reliability helpers — introduced in 0.3.1

- `store-read --store PATH`: report a bounded shared text store base hash/size.
- `store-publish --store PATH --content FILE --base-hash HASH`: cooperative
  conflict-aware publication; 2 on stale base/error, no forced overwrite.
- `lessons-search ... --diverse`: opt-in deterministic deduplication/Jaccard ranking.
- `service-status --health-file FILE --service NAME`: read advisory circuit status.
- `service-probe ...`: reserve a half-open safe-observation lease; 0 allowed,
  1 held, 2 invalid/error. No external request is made.
- `service-record ... --http-status N` or `--outcome success|transient|terminal`
  records the caller's actual observation, with optional `--retry-after SECONDS`.
- `impact --source-root PATH --symbol NAME`: read bounded Python AST/lexical
  impact and test candidates without importing project code or initializing state.

These commands do not modify the mission lifecycle. Store publication and health
updates write only the explicitly selected auxiliary files and persistent locks.
Read [reliability semantics](reliability-patterns.md) for resource limits,
process-group cleanup, journal caps, ranking, probe timing and uncertainty.

## 0.3.2 quality and learning commands

- `evidence-audit`: read-only schema-3 sufficiency gaps; return 0 means report
  generation. Inspect all_sufficient and criteria.
- `criterion-review ... --evidence-kind KIND` (repeatable): required when an
  acceptance item opts into evidence_kinds. Kinds: existence/content/behavior/
  integration/manual. Labels require real inspection; they are not proof.
- `diagnose`: recorded-fact failure classes and recovery-first next checks.
- `lesson-audit --record FILE [--as-of ISO]`: advisory validity/age/contradictions.
- `analysis-key --source-root PATH --query TEXT --policy ID --input RELPATH`: build
  a derived-analysis scope fingerprint; repeat --query and --input when needed.
- `cache-save ... --cache FILE --report JSON --redacted`: explicit auxiliary
  cache publication. No frozen mission file may be used as the cache destination.
- `cache-check ... --cache FILE [--max-age 86400]`: reuse_allowed (0), refresh (1),
  invalid/error (2); never grants execution or substitutes verification evidence.

See [semantics, formats and limits](quality-and-learning.md). The draft template
is supplemented by `templates/change-necessity.md`; no planning/approval gate is
added. `evals/run_behavioral.py` compares CLI scenarios separately from imported
agent-run reviews and refuses missing scenarios or incompatible baselines.

## Five-pass 0.3.2 corrective review

Known-full schema-3 journals refuse verification before any command runs.
Cache save/check perform postflight scope/input checks; detected drift cannot
publish or return a reusable report. Lesson dates accept absent/null as unknown,
but reject malformed falsey values and invalid explicit as-of timestamps.
The behavioral runner uses optimization-safe functional checks and atomically
publishes output without overwriting inputs/baselines/code (including aliases),
retaining existing report permissions. That review retained version 0.3.2. See the release
validation history for reproduced defects and actual results.

## Modular installation

The CLI and wrappers require the complete `scripts/mission_control/` package beside `scripts/mission.py`, plus the skill-root `VERSION`. Commands, working-directory semantics and checkpoint formats are unchanged. Analysis cache engine bindings include every package Python source file; old bindings become stale.

Implementation responsibilities are separated into contract/validation, approvals, observations/coverage/recovery, storage/journal/publication, and operational-helper modules. `mission_control/cli.py` retains the central locked transition/commit sequence to preserve ordering. Imports between cooperating functions are explicit and resolved when called. Legacy fault injection uses a test-only adapter; the production entrypoint exports only `main`.

Cache publication refuses output or lock paths that alias declared inputs, the derived report, VERSION, the entrypoint or installed package sources (including existing hardlinks and resolved symlinks). Validation runs before lock creation and again before publication. This prevents observed alias overwrites; it is not a filesystem sandbox and cannot eliminate noncooperating path-replacement races.


## Declared artifact containment (schema 3)

Optional mission-level `"allowed_paths": ["out", "build"]` restricts declared artifacts to workspace-relative prefixes. When a contract declares allowed_paths, every step artifact path must stay inside it: `file`/`not_file`/`grep` check paths, `effects.reads`, `effects.writes` and `watch`. Prefixes match path components: `out/result` is allowed, `outside/result` is not. Prefix paths themselves are included.

Omitting the field preserves existing behavior. `["."]` permits the whole workspace. An explicitly declared list must be nonempty, contain unique nonblank strings and use relative paths without parent traversal; `.` is supported as the whole-workspace prefix. Declared artifact paths also reject absolute paths and parent traversal, even with `["."]`.

`validate` checks lexical containment and resolves paths against the caller's current workspace directory; run it from the intended workspace. `init --workspace PATH` resolves against that selected workspace before publishing the contract/checkpoint. Nonexistent artifacts are permitted, but resolved symlink escapes and unresolvable loops are rejected with exit 2 and an `escapes allowed_paths` diagnostic. A rejected initialization does not overwrite an existing contract.

This is declaration validation at validate/init, not a sandbox or ongoing filesystem monitor. It does not inspect shell strings or enforce access by `exec`, `exit0`, `test` or external tools. Symlinks can change after validation; existing observation/approval safeguards remain separate. Controlled/autonomous policy, recovery and journal formats are unchanged. Schema-2 lifecycle behavior is unchanged.

Containment compatibility: whole-workspace prefixes normalize `./` to `.`. Filesystem checks may name the workspace root (`file .`) when a whole-workspace prefix is allowed; a restricted prefix still rejects that root. `not_file` paths below regular files remain valid declarations: the check reports no directory entry. These cases do not relax absolute-path, traversal or symlink-escape rejection. Existing effects/watch path validation remains unchanged.

The default mission root is `.mission`, including repeat history `.mission/state/call_hashes.txt`. Write lessons, decision logs and retained metrics under the same selected root. For existing legacy data use `--mission mission`; no automatic move/merge occurs. If using an alternate root with the repeat wrapper, set `NO_PROGRESS_STATE=<selected-root>/state/call_hashes.txt`.


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
[execution-context workflow](execution-context.md) for a selected mission's brief,
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


## Using the controller after skill activation

Loading instructions does not execute init/start. For project-changing missions,
follow [controller activation](controller-activation.md): select and inspect the
mission root; restore existing status/handoff or validate/init a new contract;
require successful start or current proof of a matching active attempt before
project mutations; then assess actual output and verify. Skill loading, a written
plan and narrative success claims are not controller evidence. Read-only requests
do not require state creation, and bootstrap metadata is a limited setup exception.
No CLI behavior, permission rule, attempt budget or state schema changes here.
