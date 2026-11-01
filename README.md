# Mission Control

Version **0.3.3** (`python3 scripts/mission.py --version`).

Author: Panos Polychronis — [ppolych@netcompany.com](mailto:ppolych@netcompany.com)

An orchestration skill for substantial controlled or autonomous goals. It coordinates work,
checks observable results, and preserves evidence across sessions.

## Layout

- `SKILL.md`: activation and workflow.
- `scripts/mission.py`: CLI entrypoint; install with the adjacent `scripts/mission_control/` package for state, validation, migration and verification.
- `scripts/*.sh`: compatible verification and repeat-detection entrypoints.
- `templates/`: contract, self-answered drafting questions, decision log, lessons, and metrics examples.
- `references/`: CLI details and research.
- `tests/`: executable regression tests.

## Quick start

Requires Python 3.10+, Bash, and Linux/WSL2/macOS. From your workspace, prepare a schema-3
contract using the supplied template, replacing the example criteria with your
actual acceptance checks. Inspect the workspace and similar past lessons first;
self-answer the [draft questions](templates/draft-contract.md), then present a
complete draft for user review instead of a sequence of intake questions.
Step count creates no gate. Controlled-mode gated steps require explicit approval
in addition to existing host authorization. Set `SKILL` to this skill's absolute directory.

```bash
python3 "$SKILL/scripts/mission.py" validate --contract contract.json
python3 "$SKILL/scripts/mission.py" init --contract contract.json --workspace "$PWD"
python3 "$SKILL/scripts/mission.py" start --step example-001
# Perform the requested work here.
# Inspect the actual artifact and record the template's manual criterion.
python3 "$SKILL/scripts/mission.py" assess --step example-001 --check 1 \
  --verdict pass --rationale 'report.txt covers the original goal and constraints; source comparison confirms accuracy'
python3 "$SKILL/scripts/mission.py" verify --step example-001
python3 "$SKILL/scripts/mission.py" criterion-review --criterion AC-1 \
  --verdict supported --rationale 'Inspected report against the original request' \
  --evidence-ref file:report.txt --evidence-ref check:example-001:1 --evidence-kind content
python3 "$SKILL/scripts/mission.py" finish
# Re-read the original request and inspect the combined output before reporting done.
python3 "$SKILL/scripts/mission.py" goal-review --verdict pass \
  --rationale 'Combined report.txt outcome answers the original request; cited source and integration evidence agree'
```

Initialization pins the workspace for lifecycle checks; later caller directories
do not change it. Missing manual assessments leave the attempt active: run
`assess`, then `verify` again without another `start`.

Lifecycle commands always use the stored mission contract; `--contract` applies
only to initialization and validation. Retries retain prior manual rationale
in history while requiring fresh assessments.

Initialization preserves an identical destination contract and rejects a different
one. Retry a contract-only interrupted initialization with the same contract.
An exhausted step leaves independent ready work available; dependent steps still
wait for verified prerequisites.

## Schema-3 evidence and recovery

Version 0.3 adds seven connected capabilities while retaining schema-2 missions:

1. Acceptance IDs map original requirements to steps and evidence references.
2. Explicit supported/unmet/unverified reviews control schema-3 completion.
3. Recovery reports require reconciliation before uncertain retries.
4. Watched file hashes invalidate stale controlled approvals.
5. Declared read/write, network, external-action and reversibility effects appear
   in approval snapshots and revision comparisons.
6. Separate linked revisions preserve parent contracts, state and budgets.
7. A hash-linked transition journal is committed atomically with each checkpoint.

The new template uses schema 3. Existing schema-2 contracts remain valid and keep
their original finish/resume behavior. No automatic schema migration or additional
autonomous approval gate is introduced. The helper does not execute declared work
commands, create a sandbox, prove semantic correctness, or guarantee exactly-once
external effects.

Read [the detailed schema-3 workflow](references/evidence-recovery.md) for the
contract fields, commands, return codes, evidence freshness and recovery limits.

Patch 0.3.1 binds supported reviews to verification-time file receipts, invalidates
old recovery reports after each reconciliation, validates ungated schema-3
workspaces, hardens persistent lock opens and rejects completion if approval
inputs change during checks. Old schema-3 declared-file evidence needs checks-only
revalidation to establish receipts; schema-2 autonomous behavior remains compatible.

## Execution modes and final review

Choose the mission-level mode in the frozen contract:

| Mode | Intended use | Skill approval policy |
| --- | --- | --- |
| `controlled` | Interactive or sensitive work | Pause before `risk: high` or `needs_approval: true` steps. |
| `autonomous` (default) | Sandboxed/CI work | Existing execution loop; no additional skill approval gates. |

Risk defaults to `low`; `needs_approval` defaults to `false`. Controlled is
selective oversight: set `needs_approval: true` on every step for full oversight.
Neither mode grants host permissions, bypasses approvals imposed by the host,
or creates a sandbox. Configure isolation separately.

A gated controlled step declares `description`, `commands` as exact argv arrays,
and its normal `verify` criteria. `commands: []` explicitly means no shell work
commands; describe intended manual/file operations in the step summary. The CLI
does not execute these work commands. It runs verification checks only through
the existing `verify` command.

`start` returns **3** and prints an `awaiting_approval` JSON request before work.
Show it to the user and wait; the digest is not a credential or user consent.
After an explicit reply, record one of:

```bash
python3 "$SKILL/scripts/mission.py" approve --step example-001 \
  --digest DIGEST_FROM_REQUEST --rationale 'User explicitly approved the displayed step'
# Or: deny with the same arguments after an explicit refusal (returns 1).
python3 "$SKILL/scripts/mission.py" start --step example-001
```

Approval persists across resume for the same contract and pinned workspace.
Since 0.2.1 the CLI rejects missing or redirected reviewed workspaces, malformed pending
requests, and manual assessments without current approval; invalid transitions
leave checkpoint state intact.
Changed commands/criteria/scope need a new mission revision. Waiting consumes
no attempts. Denial blocks the step for the revision without spending an
execution attempt or automatically retrying; independent ready work remains
available. See [approval details](references/commands.md#controlled-mode-approval-policy).

Run start → work → assess/verify → recover → finish within the chosen mode,
existing scope, and permissions. After finish, compare the combined artifacts
with the original user goal, including anything omitted from the draft. Record
`goal-review --verdict pass|fail --rationale TEXT`. A failure returns 1 and sets
`blocked` while preserving step evidence and budgets; explain the gap and propose
recovery. Never report success based solely on individually passing steps.

Schema-2 `finish` remains compatible and sets step-level `done_verified`; agents
following the skill also perform the final review before reporting success. The
CLI records a judgment, not an automatic semantic evaluation. Schema 3 additionally
requires current supported acceptance reviews before finish. An optional final
`goal-check` contract step can strengthen integration coverage.

Only verified steps can complete. Failures return a nonzero status. Default
attempt budgets are bounded; use `status` to inspect saved evidence and `resume`
to invalidate completion before rechecking interrupted work. Use `start --revalidate`
for those checks: execution budgets remain intact and external actions must not
be repeated. Deterministic checks fail fast; evidence records identity, result,
time and pinned mission workspace. Lifecycle subprocess output is discarded; definitions
and rationale are stored verbatim and must not contain secrets.

`block` parks only the active step; it cannot reopen completed work or change
a different pending step. Use `resume` to reopen completed work so downstream
completion is invalidated before revalidation.

See [CLI reference](references/commands.md) for manual assessments, migration,
configuration, and exit labels. Existing unversioned missions require explicit
migration into a new destination; originals remain untouched. Migration stages
the complete output before publishing it, so a failed write can be retried
without a partial destination. After an abrupt exit, rerun migration to the same
destination; it recovers stale staging under a destination lock.

## Lessons and skill improvement

Read relevant prior lessons before drafting, and turn them into observable
criteria. Retain at most two reusable lessons per mission in `.mission/lessons.md`
or an established shared store. Non-done exits receive a short retro identifying
the failure, any weak criterion, and the next-time correction. Write an
checkpoint/journal-derived exit snapshot using `metrics`; retain exports in
`.mission/metrics.jsonl` deduplicated by exit_id. Host token usage and human
interventions remain null when unavailable. Do not sum cumulative resumed snapshots.

After each five distinct mission records, review recurring lessons in
[skill learnings](references/skill-learnings.md). Promote supported corrections;
future behavior-changing promotions require a new release and tests. Version
0.3 adds evidence/recovery schema 3 on top of the 0.2 controlled-mode policy;
existing schema-2 missions and autonomous approval defaults remain compatible. No mission histories or
improvements have been fabricated. See [workflow details](references/agentic-workflow.md)
for the templates, counting rules, and evidence requirements.

## WSL2

Run with Linux Python inside your WSL distribution. See [WSL setup](references/wsl.md)
for installation, Windows path conversion, line endings, and filesystem guidance.
JSON inputs accept UTF-8 with or without a BOM and Windows CRLF line endings.
The release version is stored in `VERSION`; new contracts use schema 3; schema 2 remains supported.

## Validation

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/verify.sh scripts/no_progress.sh
shellcheck scripts/*.sh
python3 -m json.tool templates/contract.json >/dev/null
```

## Operational helpers (introduced in 0.3.1)

- `metrics`: deterministic JSONL-ready projection of committed state and journal.
- `handoff`: structured goal, next-work and evidence pointers for another session.
- `lessons-search --lessons-root PATH --query TEXT`: bounded historical matches
  with source paths and line numbers, usable before initialization.

All are read-only; they do not execute work, approve steps, or append journal
events. See [continuation and observability](references/continuation-and-observability.md)
for progress versus live waits, bounded polling, safe retry limits and export
semantics. Bug audits use [the evidence rubric](references/review-quality.md).
The metrics template now describes a metrics event rather than a contract.

## Reliability additions (introduced in 0.3.1)

Verification subprocesses now clean up their process groups after timeout or exit.
Checkpoint/journal read and write limits prevent unbounded, unresumable state.
Shared lessons can be published with digest-based conflict checks. Optional
`lessons-search --diverse`, advisory `service-status`/`service-probe`/`service-record`,
and read-only `impact` add selective memory, outage-aware safe observation and
code/test candidates. No approvals, recovery rules or execution budgets are relaxed.
See [the commands and limits](references/reliability-patterns.md).

## 0.3.2 — Quality, evidence and learning

Implemented in order: behavioral regression baseline, optional expected evidence
kinds and `evidence-audit`, read-only `diagnose`, lesson validity audit, scope-bound
derived-analysis caching, and a self-answered refactor-necessity template. Existing
frozen contracts and approval/recovery/budget rules remain compatible.

```bash
python3 evals/run_behavioral.py --baseline evals/baseline-control-plane-v031.json
python3 scripts/mission.py evidence-audit --mission .mission
python3 scripts/mission.py diagnose --mission .mission
```

The actual CLI baseline/comparison is 6/6 with no regression. It is not an LLM
autonomy benchmark; actual agent runs require separate reviewed artifacts.
Evidence kinds and lesson assessments are explicit judgments, not automatic
semantic truth. Cache hits never transfer approvals or verification receipts.
See [quality and learning](references/quality-and-learning.md) and
[the agent evaluation protocol](evals/agent-scenarios.md).

### Python package layout

Run `python3 scripts/mission.py` as before. Copy/install the complete `scripts/` directory and `VERSION`; copying only the entrypoint is insufficient. The adjacent `mission_control/` package uses only the standard library. Python source and test files are limited to 400 physical lines each.

Schema-3 contracts optionally restrict declared artifact paths with `allowed_paths`, for example `["out", "build"]`. Omit it or use `["."]` for the whole workspace. See [declared artifact containment](references/commands.md#declared-artifact-containment-schema-3); this policy does not sandbox commands.


## 0.3.3 — Modular packaging and declared artifact containment

This release packages the completed refactor and corrective reviews previously validated under 0.3.2:

- The CLI requires the complete `scripts/` directory and root `VERSION`; every Python file stays within 400 physical lines.
- Optional schema-3 `allowed_paths` constrains declared filesystem checks, effects and watch paths at validate/init. Omitted policy retains existing behavior; whole-workspace prefixes support `.` and `./`.
- Cache publication protects inputs, reports and installed implementation files from output/lock aliases. Public helper docstrings and filesystem-check compatibility are preserved.

Controlled/autonomous policy, recovery, checkpoint/journal formats and contract schema versions remain unchanged. Containment validates declarations; it does not sandbox commands or monitor later filesystem changes. See [validation history](references/operational-validation.md) for actual test results. Historical 0.3.1/0.3.2 evaluation files remain labeled with the versions they observed.

Current test results and their history are kept only in the [validation record](references/operational-validation.md).

Actual model behavior has not been benchmarked; see [Nestor trials](evals/agent-scenarios.md).

## Contract and retry behavior

- `validate`, `init`, `revise` and `revision-diff` refuse unknown contract and step fields, so a misspelled `needs_approval` cannot silently remove a gate. Prefix comments with `_`. Already frozen contracts keep working.
- Step `verify_timeout` (seconds, up to 86400) overrides `VERIFY_TIMEOUT`, whose default is 60. Timeouts are reported on stdout and count as failures.
- `recover --resolution applied_incorrect` allows a budgeted corrective attempt after a failed verification of reversible work without external actions.
- Declared writes over 1 MiB and directories get metadata receipts: size/mtime/ctime/mode, or a no-follow tree manifest up to 50,000 entries. These are weaker than SHA-256 and read no file bytes. Watched inputs remain exact-hash only.
- Read-only reports take no lock, so they work during a running `verify`. No command except `init` creates a missing mission directory.
- `finish` still sets `done_verified`, and `status`, `handoff` and `diagnose` report `goal_review_status` until the review is recorded.
- `resume` from `human_abort` requires `--rationale`, kept in `resume_history`.


## Workspace runtime layout

New missions use one hidden directory by default:

```text
.mission/
  contract.json
  state/
    progress.json
    call_hashes.txt
  decision-log.md
  lessons.md
  metrics.jsonl
```

The CLI creates contract/checkpoint and repeat state; the agent writes decision logs, lessons and retained metrics only when needed. Use this same selected mission root for all auxiliary artifacts. Old `mission/` directories are not moved or merged automatically: open them explicitly with `--mission mission`. The repeat wrapper defaults to `.mission/state/call_hashes.txt`; for an explicitly selected alternate root, set `NO_PROGRESS_STATE` to that root's `state/call_hashes.txt`. Do not create a second runtime directory for notes or exports.


## Diagnostics and reproducible packaging

Use `handoff` or `diagnose` to identify the installed CLI/fingerprint, selected mission root, missing manual assessment indices and dependency blockers. Continuation suggestions are advisory and never grant retry or approval. These reports do not identify Nestor's UI mode.

```bash
python3 scripts/package_release.py
# Or choose a separate archive location:
python3 scripts/package_release.py --output /tmp/mission-control.zip
```

The build emits `mission-control.zip` and its `.zip.sha256` sidecar, embeds `MANIFEST.sha256`, fixes ZIP metadata for reproducibility and excludes caches/generated archives/checksums. It verifies the manifest, extracted CLI/wrappers, contract validation and a disposable lifecycle using only `.mission/` before publication. Reproducibility assumes identical source bytes and file modes under the same compression implementation. A persistent nonblocking lock serializes cooperating publishers. Handled replacement errors restore the previous pair; failed restoration retains recovery files and reports their directory. Abrupt termination between replacements can still leave a mixed pair, so verify the checksum before distribution.


## Focused execution context

Pin one mission directory and restore its live checkpoint after interruption.
Draft observable GIVEN/WHEN/THEN scenarios, map requirements to step/check evidence,
and keep a small brief only for the active step when useful. Record consequential
decisions with evidence, rationale, cost if wrong and a revisit trigger. The
[workflow reference](references/execution-context.md),
[execution brief](templates/execution-brief.md) and
[acceptance scenarios](templates/acceptance-scenarios.md) provide the formats.

`evidence-audit` adds structural traceability for acceptance IDs, contributing
steps, zero-based check indices/kinds and declared outputs. Shared checks remain
explicitly step-level links. Unmapped support steps are reported rather than
rejected. Structural links are not behavioral proof or an additional approval
gate; existing evidence freshness and goal review still determine outcomes.
Store optional briefs and scenario notes under the same selected `.mission/`
root. Neither notes nor a decision ledger can change a frozen contract or supply
approval. Review the combined user outcome before reporting success.


## Compact continuation and isolated Nestor trials

`python3 scripts/mission.py handoff --compact` returns at most five step rows,
status counts, the active step, an advisory next-ready identifier and omitted-row
count. Use full `handoff` for complete dependencies/evidence/approval details.
Compact output grants no authority and spends no attempts.

Report-local active-step and requirement indexes avoid repeated structural scans.
File observations, receipts, approvals and final freshness checks are not cached.

Prepare independent UI trials with:

```bash
python3 evals/nestor_trials.py prepare --output /tmp/nestor-mission-trials
python3 evals/nestor_trials.py summarize --review /tmp/nestor-mission-trials/review.json
```

Preparation creates six disposable case directories and claims zero actual runs.
Open each case as a new Nestor session, explicitly choose Agent mode, follow its
request/reviewer instructions and retain the actual trace/final state. Record
model, session, independent verdict and observed metrics in review.json. Unknown
interventions/attempts/outcomes stay null; fixture preparation and CLI tests are
not model benchmarks. See [Nestor trials](evals/agent-scenarios.md).


## Skill activation and controller use

Loading mission-control supplies workflow instructions; it does not run its Python
controller. For project-changing missions the agent must inspect the selected
.mission root, restore a valid existing checkpoint or validate/init a new contract,
and obtain a successful start/current active-attempt result before project
mutations. It then assesses actual output and verifies the step. Read-only requests
remain read-only, existing authorization avoids routine extra approval, and
bootstrap writes are limited to mission metadata. See
[controller activation](references/controller-activation.md).

These prompt rules do not install a Nestor execution hook. Host enforcement is
needed to guarantee tool-level compliance; actual agent behavior must be reviewed
separately from controller tests. No live session is changed by this update.
