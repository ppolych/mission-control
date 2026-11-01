# Quality and learning

## Contents

- [1. Behavioral baseline and regression checks](#1-behavioral-baseline-and-regression-checks)
- [2. Evidence kind requirements and sufficiency gaps](#2-evidence-kind-requirements-and-sufficiency-gaps)
- [3. Recorded-fact failure diagnosis](#3-recorded-fact-failure-diagnosis)
- [4. Lesson validity, contradictory evidence and age](#4-lesson-validity-contradictory-evidence-and-age)
- [5. Scope-bound derived-analysis reuse](#5-scope-bound-derived-analysis-reuse)
- [6. Justify refactors and added maintenance surface](#6-justify-refactors-and-added-maintenance-surface)
- [Release validation](#release-validation)

Implemented in order: behavioral baseline, evidence sufficiency, failure
diagnosis, lesson validity, analysis reuse, and change-necessity guidance.
All advisory reports remain separate from permissions, execution and semantic
truth. Existing schema-2/3 contracts remain compatible; new fields are opt-in.

## 1. Behavioral baseline and regression checks

```bash
python3 evals/run_behavioral.py --baseline evals/baseline-control-plane.json \
  --output /tmp/control-plane-result.json
```

The 0.3.1 baseline was actually run before quality changes: six isolated CLI
scenarios passed. The 0.3.2 comparison also passed all six with no regression.
These probes exercise incomplete finish, missing assessment, autonomous approval
policy, stale receipts, interrupted inspect recovery, and denial across resume.
They do not call a model or prove that a prompt produces better autonomous work.

`--baseline` requires the same suite/scenario set and reports case-level pass-to-fail
regressions. Missing/duplicate cases, incompatible suites and changed scenario
digests are rejected rather than hidden by aggregate accuracy. A failing current
case causes exit 1 even when the baseline already failed it. Exit 2 denotes invalid
input. `--output` explicitly saves a report; default output is stdout. Evaluation output is published atomically and cannot overwrite the baseline,
agent-grade input, assessed CLI or runner, including symlink/hardlink aliases.
Existing report permissions are preserved; failed replacement leaves the old
report intact. Functional probes remain active under python -O.

For actual agent evaluations follow `evals/agent-scenarios.md`, then import
operator-reviewed grades:

```bash
python3 evals/run_behavioral.py --agent-results /known/review/grades.json \
  --output /known/review/result.json
```

Use --baseline with a previous agent report to compare actual reviewed runs.
Do not compare an agent run to the CLI baseline. Unverified grades are not passing;
passing grades need evidence artifacts. The importer validates/hashes files, not
their semantic truth. Current release results include no actual model benchmark.

## 2. Evidence kind requirements and sufficiency gaps

Schema-3 acceptance items optionally declare `evidence_kinds`, a unique list of
`existence`, `content`, `behavior`, `integration`, or `manual`. Example:

```json
{"id":"AC-1","description":"Output implements the requested behavior", "evidence_kinds":["behavior","integration"]}
```

Record declared proof types during review:

```bash
python3 "$SKILL/scripts/mission.py" criterion-review --criterion AC-1 \
  --verdict supported --rationale 'Inspected behavior and integration results' \
  --evidence-ref check:example-001:1 --evidence-kind behavior --evidence-kind integration
python3 "$SKILL/scripts/mission.py" evidence-audit
```

For opted-in requirements, supported review needs all required kinds; coverage
also treats missing kinds as unverified. Rationale and existing current receipts,
passed checks and artifact references are still required. Declarations do not
turn an existence check into behavioral proof: the reviewer must inspect actual
results and justify each label. No heuristic confidence percentage is assigned.

`evidence-audit` is read-only and schema-3 only. It reports missing kinds and
unmet/missing/stale reviews. Exit 0 means report generation, not sufficiency;
inspect all_sufficient and the gaps. No requirements are added to legacy contracts,
no existing approvals transfer, and no criteria are weakened. The supplied new
contract template requests content evidence. Older frozen contracts stay unchanged.

## 3. Recorded-fact failure diagnosis

`diagnose --mission PATH` is read-only and returns per-step kinds, dispositions
and next checks. It uses actual error types/statuses: command unavailable,
permission/policy blocker, timeout, signal, missing file, manual unmet, generic
command failure or unknown. It does not infer build/test/lint semantics from an
arbitrary nonzero exit code and does not retain raw command output.

Denial remains denial; approval waiting remains a user decision. A schema-3
recovery_required flag takes precedence over retry suggestions. Reports always
set retry_authorized false. Diagnose assists the agent; the existing lifecycle
still enforces current approvals, recovery, workspace identity and budgets.

## 4. Lesson validity, contradictory evidence and age

Use optional `templates/lesson-record.json` for a structured record alongside
existing Markdown lessons, without migrating/rewriting the shared store:

```bash
python3 "$SKILL/scripts/mission.py" lesson-audit --record /known/lesson.json
```

A record has lesson_id, context, statement, optional last_checked (timezone-aware
ISO; absent/null means unknown, other invalid values are rejected), and up to 256 uniquely identified evidence entries with id, source_ref and
effect supports|weakens|contradicts|stales. No supports → unsupported. Support plus
contradiction, weakening, explicit staleness, unknown last-check date, future date
or a last check older than 30 days → needs_review. Otherwise the advisory status
is supported_observations. `--as-of ISO` makes historical reviews reproducible.

The 30-day heuristic requests review, not automatic deletion or scientific
confidence decay. Evidence references are caller descriptions; recheck actual
owning sources before reuse. Preserve counterexamples and supersede a lesson
explicitly rather than deleting its history. At most two reusable lessons per
mission remains the policy. Write updates through conflict-aware store publication.

## 5. Scope-bound derived-analysis reuse

```bash
python3 "$SKILL/scripts/mission.py" analysis-key --source-root /known/project \
  --query 'impact save' --policy read-only-scope-v1 --input src/app.py
python3 "$SKILL/scripts/mission.py" cache-save --source-root /known/project \
  --query 'impact save' --policy read-only-scope-v1 --input src/app.py \
  --cache /known/cache/impact.json --report /tmp/derived-report.json --redacted
python3 "$SKILL/scripts/mission.py" cache-check --source-root /known/project \
  --query 'impact save' --policy read-only-scope-v1 --input src/app.py \
  --cache /known/cache/impact.json
```

The binding includes canonical workspace, exact query list, caller-declared policy
scope, observed input hashes/modes (including dirty edits), release and helper
source hash. At least one explicit input is required; declare every source that
could affect the analysis. There is no inferred complete dependency graph or
host-policy discovery. Missing inputs cannot seed a reusable cache; deletion after caching causes
refresh. Unreadable inputs return an error. Changed scopes require fresh
analysis; unavailable observations cannot be used.

Cache-save accepts a bounded 64 KiB JSON object and explicit redacted assertion.
Known raw-log/payload/reasoning and lifecycle-authority fields are refused.
This is not an automatic secret detector: the caller must review/redact summaries.
Cache files are bounded to 1 MiB, published atomically under a persistent lock;
report digests detect accidental corruption, not malicious rewriting. Do not
store approvals, verification receipts or acceptance reviews for reinjection.

Cache-save rechecks its complete binding immediately before publication under
the cache lock; detected drift refuses publication. Cache-check rechecks binding
after reading the cached record and returns refresh_required without the report
on drift. These observations are not filesystem-wide isolation; an arbitrary
concurrent edit after the final check remains possible.

Cache-check is read-only. Matching binding, intact report and age 0..max_age yields
reuse_allowed (0) and the derived report. Otherwise refresh_required (1) omits
the report; malformed/unavailable inputs are 2. Default maximum age is one day,
configurable 1..604800 seconds. Future timestamps are not reusable. No TTL or
cache hit proves current verification or grants execution. Explicit cache files
are auxiliary; never point them at frozen contracts/checkpoints. CAS-store writes
are available if multiple reviewers must preserve concurrent human edits.

## 6. Justify refactors and added maintenance surface

Before proposing a refactor/new abstraction, self-answer
`templates/change-necessity.md`: goal served, observed problem, focused correction,
incremental alternative, operational/maintenance cost, decision and validation.
Use impact/LSP candidates to identify actual affected callers/tests and verify
bindings. Choose an implementation that fully satisfies the original authorized
goal; do not shrink it to avoid complexity or add unrelated refactors for style.

This is agent guidance, not a score or approval gate. Supported refactoring remains
allowed within scope. Record the rationale in the draft/decision log; introduce
a revision when frozen acceptance or declared effects must change. No automatic
scope expansion, budget increase or numeric architecture threshold is introduced.

## Release validation

Control-plane comparison: 6/6 with no
regression against the pre-change 0.3.1 baseline. The separate agent-review
importer was tested with synthetic artifacts; no actual LLM benchmark was run.
See operational-validation.md for the combined quality smoke and all checks.
