# Repository Guidelines

## Project Structure & Module Organization

Mission Control 0.3.3 is a Nestor orchestration skill with a Python core and Bash entrypoints.

- `VERSION` is the canonical release; keep skill metadata consistent. Contract schemas 2 and 3 are separate from the release version.
- `SKILL.md` is the concise agent entrypoint; workflow details belong in `references/`.
- `scripts/mission.py` is the CLI entrypoint; `scripts/mission_control/` handles lifecycle, verification,
  migration, goal review, and digest-bound controlled-mode approvals.
- `templates/` supplies contracts, five drafting questions, decision logs, lessons, and metrics entries.
- `references/skill-learnings.md` records evidence-based skill improvements.
- `tests/test_mission.py` preserves lifecycle compatibility; `tests/test_controlled.py`
  covers risk-aware approval, denial, strict validation, and resume behavior.
  `tests/test_controlled_review.py` covers transition, workspace identity, and
  pending-snapshot regressions from the five-pass review.
- `tests/test_v03.py` exercises schema-3 acceptance, effects, watch digests,
  recovery, revisions and transactional journal behavior in temporary missions.
- `tests/test_v03_review.py` covers the second five-pass review: verification
  receipts, recovery replay, ungated workspace identity, lock files and approval
  drift during checks, including compatibility with pre-receipt checkpoints.
- `references/evidence-recovery.md` owns the detailed schema-3 workflow.
- `tests/test_agentic_tools.py` covers read-only metrics/handoff exports, selective
  lesson retrieval, legacy state, malformed journals and the corrected metrics template.
- `references/continuation-and-observability.md` and `references/review-quality.md`
  own continuation, bounded polling/retry, export and evidence-based audit rules.

Runtime artifacts belong in the consuming workspace’s `.mission/` directory, outside this skill’s source.

## Build, Test, and Development Commands

Requires Linux (including WSL2) or macOS, Python 3.10+, Bash, standard Unix tools, and Unix locking. No pip dependencies are required.

```bash
python3 scripts/mission.py --version
python3 -m unittest discover -s tests -v
python3 scripts/mission.py validate --contract templates/contract.json
bash -n scripts/verify.sh scripts/no_progress.sh
shellcheck scripts/*.sh
```

Run from the repository root. Focused example: `python3 -m unittest discover -s tests -k GoalReviewLifecycle -v`.

## Coding Style & Documentation

Use snake_case identifiers, quoted shell expansions, and two-space JSON indentation. Match surrounding code; avoid unrelated reformatting. No formatter is configured. Keep instructions, README, templates, and command documentation consistent. Honor LF checkout rules; read JSON as UTF-8 with optional BOM and write UTF-8/LF independently of locale.

## Testing & Workflow Guarantees

Add regressions before fixing bugs or changing CLI behavior. Use temporary workspaces and isolated repeat history. Preserve the existing test suite, single-active-step design, frozen contracts, pinned workspace, exact argv boundaries, and execution budgets. Test migration faults/crash recovery; never unlink persistent locks or clean unrelated staging.

Inspect workspace and relevant lessons before presenting a complete contract draft. Use the self-answered template instead of adding an unnecessary planning CLI. Preserve host authorization. Step count creates no gate. Autonomous keeps existing
behavior; controlled pauses before high-risk or explicitly gated steps. Waiting
spends no attempts, approvals bind to contract/workspace digests, and denials
block the step for that revision without retry. Test independent ready work and
legacy checkpoints. See references/commands.md for lifecycle and return codes.

## Controlled-Mode Regression Rules

- Validate single-active-step and dependency constraints before handling a denied
  retry; rejected transitions must leave the checkpoint bytes unchanged.
- Before approving or starting gated work, recording its manual assessment, or
  verifying it, require the pinned workspace to exist and resolve to its stored
  canonical path. Refusing work remains possible when the workspace is missing.
  This preflight is not a sandbox or protection against filesystem races.
- Both `assess` and `verify` require a current contract/workspace-bound approval
  for gated controlled steps. Host permissions remain independently necessary.
- Validate pending requests completely: step snapshot, request status, absolute
  workspace, strict revalidation boolean, and digest. Reject malformed snapshots
  without silently repairing them or consuming attempts.
- Install/copy the complete `scripts/` directory with `VERSION`; the entrypoint requires its adjacent `mission_control` package. Keep every Python file at most 400 physical lines. Preserve autonomous defaults, exact argv, and legacy recovery.
- Use isolated temporary missions for regressions; never exercise failure paths
  against operator state. Run the full suite plus skill/template validation,
  Bash syntax checks, and ShellCheck. Record actual results in the release notes.

## Schema-3 Invariants

- Preserve schema-2 lifecycle behavior. Never upgrade a frozen contract in place;
  revisions publish a separate directory with parent snapshots and lineage.
- Every acceptance item must map to steps. File existence alone is not behavioral
  proof: record explicit supported/unmet/unverified verdicts with real evidence.
  Finish and passing goal review require current supported schema-3 coverage.
- Supported review requires current verification receipts for mapped declared
  outputs and watched inputs. Do not re-bless changed artifacts with old checks.
  Older schema-3 evidence without receipts requires checks-only revalidation.
- Watched inputs bind controlled approvals; declared output/input evidence changes
  invalidate acceptance reviews. Observations are bounded, no-follow file hashes,
  not backups or a sandbox. Declared effects do not enforce tool permissions.
- Uncertain executions using inspect retry policy require report-bound recovery.
  Completed recovery authorizes checks only; partial/unknown remains blocked.
  No recovery refunds attempts, executes work, or overrides a user denial.
- Recovery reports bind status, revalidation eligibility and reconciliation
  sequence. A prior decision invalidates the old report digest even if file hashes
  did not change; obtain a current report before the next reconciliation.
- Every schema-3 assessment/verification validates the canonical workspace even
  when ungated. Successful verification rechecks workspace and gated approval
  identity before committing completion; checks may already have run on refusal.
- Commit transition events and checkpoint state atomically in one file. Validate
  the hash chain before mutation; readonly commands and invalid requests append
  nothing. This local unkeyed journal is diagnostic, not authenticated evidence.
- Mission and publication locks use regular persistent inodes, no-follow and
  nonblocking opens, with no truncation or unlink. Refuse symlink/FIFO locks and
  preserve lock contention behavior. Test these only with disposable fixtures.

Keep legacy finish behavior compatible. Agents must review the combined outcome after finish; failed goal review blocks success without discarding step evidence. Repeated finish must preserve exit identity.

Retain at most two lessons per mission. Derive metrics with the read-only helper;
retain exports explicitly, deduplicated by exit_id. Unknown tokens and human
interventions stay null. Do not convert recorded approval counts into invented
human interactions. Handoff and lessons are context, not live evidence or authority. Review five distinct missions, not resumed exit snapshots. Promote recurring lessons only with evidence; behavior-changing promotions require tests and a documented release bump.

## Commits, Pull Requests & Security

Use imperative subjects; describe behavior, validation, and limitations. Exclude secrets from recorded definitions and rationale. WSL uses Linux Python and quoted Linux paths; follow `references/wsl.md`. Do not claim untested mounted-drive compatibility.

## Current operational additions

Version is 0.3.3 by explicit author instruction. Keep VERSION, skill metadata
and current documentation consistent; do not bump it again without permission. Keep metrics/handoff/search/impact read-only and all helpers dependency-free.
Store publication and service observations may update only explicitly selected
auxiliary files under persistent locks; they grant no lifecycle permissions. Search only
a known bounded lessons scope, with no-follow regular-file reads and source
references. Preserve active jobs on polling timeouts; retries never override
recovery, denials or budgets. Use the review rubric and disposable reproductions.

## Reliability additions at unchanged version

`tests/test_grok_patterns.py` covers process-group cleanup, cooperative shared-store
CAS, checkpoint/journal limits, optional diversity ranking, advisory circuit
breakers and bounded code-impact candidates. Keep timeout cleanup separate from
recovery judgments: a killed process group does not prove external actions were
not applied. Do not retry side effects via service probes. Check both state read
and write caps before publishing a checkpoint, preserve the old file on refusal,
and never truncate a journal to bypass limits. Treat impact/search results as
source-linked candidates, not proof or resolved symbol bindings.

## Quality additions in 0.3.2

`tests/test_quality032.py` covers optional evidence-kind requirements, read-only
sufficiency/diagnosis, contradictory/stale lessons, analysis cache scope and raw
payload refusal, invalid input preservation and behavioral report validation.
Run `python3 evals/run_behavioral.py --baseline evals/baseline-control-plane-v031.json`
in addition to the full unittest suite. CLI scenario conformance and actual
operator-reviewed agent runs are separate suites and cannot be compared together.
Do not claim model-autonomy gains without actual runs and review artifacts.

Evidence kinds are opt-in schema-3 requirements with reviewer declarations.
Never change existing frozen contracts or infer behavioral proof from existence.
Diagnoses authorize no retry; cache hits transfer no approvals or verification
receipts. Keep cache/redaction assertions and lesson age judgments explicitly
advisory. Use change-necessity.md to justify refactors/new surface within the
FULL original goal; no scoring-based scope reduction or new approval gate.

## Five-pass 0.3.2 review rules

`tests/test_review032.py` covers capacity preflight, cache input drift, strict
lesson timestamps, optimized evaluator execution, and alias-safe output writes.
A known-full journal must refuse verification before running checks. Recheck cache
bindings after reading derived data and before publication; a stale lookup must
not return a report. Dates that are absent/null are unknown; malformed falsey
values are errors. Behavioral invariants must not depend on Python assert, which
-O disables. Evaluation output cannot overwrite its inputs, baseline, assessed
CLI or runner, including aliases; retain old report bytes on write failure and
preserve existing permission bits. Document observation-race limits honestly.

## Modular Python layout

Keep modules focused on one responsibility and below 400 physical lines, including tests. In `scripts/`, lines stay within 160 characters and functions within 120 lines (`tests/test_review_fixes.py`). CLI syntax and checkpoint formats remain stable. Legacy fault-injection tests use `tests/core_adapter.py`; new tests should patch the owning module directly. Cache engine identity covers the entrypoint and every package source file.

## Optional declared artifact containment

Schema-3 `allowed_paths` is optional; omission preserves legacy behavior and `["."]` permits the workspace. Validate every declared filesystem check path, read/write effect and watch against component-based prefixes; resolve against the caller workspace for validate and the selected pinned workspace before init publication. Reject traversal, absolute paths and symlink escapes/loops without overwriting an existing contract or publishing state. This is declaration policy, not command sandboxing or ongoing monitoring. Keep schema-2, modes, recovery and journal formats unchanged. Regressions live in tests/test_allowed_paths.py.

Containment compatibility regressions live in tests/test_allowed_paths_review.py. Keep workspace-root filesystem checks valid for whole-workspace policies, normalize equivalent root prefixes, and distinguish a non-directory parent from a containment escape. Retain legacy effects/watch validation and all traversal/symlink restrictions.



## Unified runtime directory

Use `.mission/` for new mission runtime artifacts, including contract, state, repeat history, lessons, decision log and retained metrics. Use the same explicitly selected mission root for agent-written auxiliary files; configure NO_PROGRESS_STATE accordingly for alternate roots. Never auto-move/merge legacy mission directories. Version remains 0.3.3 by current author instruction. Regressions: tests/test_mission_directory.py.

## Agent guidance and release tooling

`handoff` and `diagnose` include advisory continuation hints and fresh installation identity. Missing/unverified assessment indices and blocked dependencies are context, not execution authority. Respect denials, stop reasons, recovery and budgets before any suggested work; never infer host mode or permission from these reports.

Cache publication must reject output/lock aliases of inputs, reports and installed code/version sources. Preserve current evidence and approval rechecks. Allowed-path prefix resolution may be shared only inside one validation call; never reuse filesystem observations across commands or commit boundaries.

Build releases with `python3 scripts/package_release.py`. Keep archive construction in `scripts/release_archive.py`, including deterministic metadata and an embedded SHA-256 manifest. Exclude generated archives, checksums and caches. Packaging must pass extracted-install smoke checks before replacing the release archive.

Test counts and release evidence belong only in [operational validation](references/operational-validation.md); do not duplicate them here. Keep version 0.3.3 unless the author explicitly requests another bump.


## Focused context and structural traceability

Pin one selected mission directory; restore that checkpoint before writing notes
or continuing after interruption. Context refresh alone must not trigger resume.
Use concrete acceptance scenarios and a small optional active-step brief. Record
consequential decisions with evidence, cost if wrong and revisit triggers; notes
grant no approval and cannot amend frozen contracts. Details belong in
references/execution-context.md and the associated templates.

The evidence-audit traceability section reports declared step/check/output links
only, without command arguments or invented per-check requirement ownership.
Shared checks remain shared and support steps are not a new gate. Structural
links never establish behavioral completion; preserve existing receipt freshness,
acceptance reviews and combined-goal review. Tests: tests/test_execution_context.py.


## Bounded reports, publication and real-agent evaluation

Collect active-work status once per report and share a call-local requirement
index between coverage and traceability. Never memoize file observations,
approvals or receipts across their existing freshness boundaries. Compact handoff
is read-only, limited to five step rows and advisory; reject --compact elsewhere.

Release publication uses a regular persistent nonblocking lock, handled-error
rollback and retained recovery files if restoration fails. Never unlink locks.
Crash-atomic ZIP/checksum pairing is not promised; require checksum verification.

Nestor trial preparation and summary live in evals/nestor_trials.py. Preparation
is not an agent run. Use new disposable sessions only; preserve unknown metrics
as null, retain real session/model/evidence and independent operator grades.
Never claim autonomy measurements from fixtures or CLI tests.


## Controller activation workflow

Skill loading is not controller initialization or active-step proof. For authorized
project mutations, inspect the selected root and restore a valid checkpoint or
validate/init a new contract; require successful start or current matching active
state before project work, then assess/verify actual results. Read-only requests
remain read-only. Bootstrap metadata is a limited exception, not project-write
authority. Preserve counters, frozen contracts, interrupted initialization and
existing permissions; do not add routine approval gates or auto-resume on context
refresh. Details: references/controller-activation.md. No host hook is implied.


## Agent-usability review rules

Regressions live in tests/test_review_fixes.py. Strict field checks run only on new
drafts (validate, init --contract, revise, revision-diff), never on frozen contracts.
Read-only reports take no lock but still refuse a non-regular `.lock` entry. Lock
contention raises `LockBusy`, an OSError. `applied_incorrect` requires a failed
verification and refuses external or irreversible effects. Metadata receipts apply
only to declared writes and file evidence refs; watched inputs stay exact-hash because
they bind approvals. `done_verified` keeps its timing for compatibility: expose a
missing review through `goal_review_status` instead of moving the label.
