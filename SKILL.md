---
name: mission-control
description: Orchestrate substantial multi-step goals with durable mission state, evidence-based verification, bounded recovery, and explicit outcomes. Use for controlled, autonomous, or multi-session work; exclude simple edits and quick questions.
metadata:
  version: "0.4.2.1"
  author: "Panos Polychronis"
  email: "ppolych@netcompany.com"
---

# Mission Control

Version 0.4.2.1. Requires Python 3.11+, Bash, and Unix locking on Linux, WSL2,
or macOS. For WSL paths and setup, read [WSL guidance](references/wsl.md).
Preserve the user's scope, existing authorization, and host permissions.

## Activate the controller

Loading this skill is not initialization. For an authorized project-changing
mission, select one absolute `.mission/` root and inspect its contract/checkpoint.
Existing checkpoint: use successful `status`/`handoff` results to restore the
current attempt; do not resume or create a competing mission just to refresh
context. No checkpoint: inspect, draft the complete contract, then successfully
`validate → init`. Preserve interrupted initialization and malformed existing data.
Before project mutations, require successful `start` or current proof that the
matching step is already `in_progress`; revalidation permits checks only. Bootstrap
metadata may be written in the selected mission root. Read-only investigation
requires no initialization and must remain read-only when requested.
After work, supply evidence-based `assess` when required and run `verify`; report
completion only from successful controller results/current state, never from skill
loading or narration. Existing authority applies without extra routine approvals.
Follow [controller activation](references/controller-activation.md) for branching,
return codes, failure handling and observable proof. These are agent rules, not a
host enforcement hook.

## Command path

Set `SKILL` to this skill's absolute directory. Every command takes `--mission PATH`
when the mission root is not `.mission`; `--help` lists all commands and flags.

```bash
python3 "$SKILL/scripts/mission.py" validate --contract contract.json
python3 "$SKILL/scripts/mission.py" init --contract contract.json --workspace "$PWD"
python3 "$SKILL/scripts/mission.py" start --step STEP
```

Do the step's work and inspect the actual result, then continue:

```bash
python3 "$SKILL/scripts/mission.py" assess --step STEP --check INDEX --verdict pass --rationale TEXT
python3 "$SKILL/scripts/mission.py" verify --step STEP
python3 "$SKILL/scripts/mission.py" criterion-review --criterion AC-1 --verdict supported \
  --rationale TEXT --evidence-ref check:STEP:INDEX --evidence-kind content
python3 "$SKILL/scripts/mission.py" finish
python3 "$SKILL/scripts/mission.py" goal-review --verdict pass --rationale TEXT
```

Exit codes: 0 success; 1 refusal, check failure or exhausted work; 2 invalid input
or transition; 3 waiting for a controlled-step decision. Failed checks report their
index and exit status, not their output; rerun the check yourself to diagnose it.

After each transition the controller prints `next (advisory): COMMAND` on stderr, and
`status`, `handoff` and `diagnose` report `next_action`. Uppercase words are placeholders.
It is guidance from recorded state: it grants no permission, and it never replaces
inspecting the actual work or a user's decision.

## Phase 0 — Inspect and draft autonomously

Inspect the workspace FIRST: relevant source, conventions, tests, existing
artifacts, and constraints. Before drafting, read lessons from similar prior
missions and the applicable [skill learnings](references/skill-learnings.md).
Turn relevant lessons into observable acceptance criteria, not extra ceremony.
Use `lessons-search` on a known store for bounded, source-linked retrieval;
recheck current sources before applying history. Use optional `--diverse` for
nonredundant results and `impact`/an available LSP to locate affected code and
tests before drafting. These are candidates, not correctness evidence. Audit
contradicted/stale lessons before reuse; justify refactors with
[change necessity](templates/change-necessity.md), preserving the full goal.

Self-answer the five questions in [the draft template](templates/draft-contract.md),
then present a COMPLETE draft contract with evidence, assumptions, dependencies,
and rerunnable checks. The user reviews, approves, or amends your draft; do not
make them co-author it through step-by-step questions. Ask only for genuinely
consequential missing requirements, alongside the otherwise complete draft.
Step count never creates a gate. Existing authorization permits ordinary work;
controlled-mode step gates below still require explicit approval.

Pin one selected mission directory and restore its checkpoint before creating
notes or acting after interruption; context refresh alone is not a reason to
resume. Draft concrete GIVEN/WHEN/THEN outcomes and map them to step/check evidence.
Use [execution context](references/execution-context.md) for mission selection,
small active-step briefs, consequence-aware decisions and combined-outcome review.

For a new mission, create a schema-3 contract from [the template](templates/contract.json). Include a
criterion testing whether the combined outcome satisfies the original goal, or
an optional final `goal-check` step. Keep requirements separate from tactics.
Optionally declare evidence_kinds per acceptance item; the new template requires
content evidence. Use [quality guidance](references/quality-and-learning.md) for
behavioral baselines, sufficiency gaps, diagnosis, lesson audits and analysis cache.
Map acceptance IDs to steps; declare exact effects, watched inputs and retry
policy. The template sets `discipline: strict`: a step that writes declares
`test_first`, or `test_first_exempt` with a reason. Choose in proportion to the task
using the [development method](references/development-method.md); [strict discipline](references/strict-discipline.md)
states what is enforced, what is a heuristic and what is only an agent statement.
A strict mission stops before a push: keep the push out of the steps, then after `finish` and a passing
`goal-review` commit, run `gate --commit SHA`, and push only if it exits 0. Read [schema-3 evidence and recovery](references/evidence-recovery.md)
when drafting, reconciling interruptions, or creating revisions.
For that new mission run `validate`, then `init`; existing contracts must not be overwritten or
weakened. New requirements need an explicit new mission revision (`revision-diff`, then
`revise` into a separate destination). Existing schema-2 missions stay compatible. Use helper
paths relative to this skill. Details: [workflow](references/agentic-workflow.md)
and [CLI](references/commands-lifecycle.md).

## Execution modes

Use `mode: controlled` for interactive/sensitive work and `autonomous` for
sandboxed/CI work (the backward-compatible default). Both preserve host
permissions and existing authorization; neither creates a sandbox.

Run `start → work → assess/verify → recover → finish`, one active step at a time.
In controlled mode, `needs_approval: true` OR `risk: high` requires a gate BEFORE
work, including verification. Declare a nonblank description and exact work
`commands` argv arrays (`[]` for no commands). On `start` exit 3, pause and show
the exact step, criteria, command arrays, pinned workspace and request digest;
wait for explicit user approval or denial. Only then record `approve` or `deny`
with that digest and the user's decision as rationale. Never self-approve,
infer approval from silence, or treat the mission's initial approval as a step
approval. An empty, dismissed, cancelled or ambiguous reply is not approval: ask
again or keep waiting. Record the user's words verbatim as the rationale; never
compose or summarize them into a decision. If you cannot tell whether the user is
present, ask and wait. After approval, rerun `start`; approval does not itself start work.

Approvals persist across resume only for the same contract/workspace digest.
Changed scope/commands/checks require a new reviewed mission revision. Denied
steps remain blocked without automatic retry, including after resume; independent
ready work may continue. Low/medium steps without `needs_approval` run without
this gate; set it on EVERY step for full oversight. Autonomous adds no skill
approval gates. Stop at verified completion or an explicit stop label. Details:
[approval lifecycle and CLI](references/commands-approval-recovery.md#controlled-mode-approval-policy).
This is an agent workflow, not a scheduler or extra permission for external actions.
`resume` from `human_abort` requires `--rationale`; use it only after the user explicitly
asks to continue.

Each check defaults to a 60-second limit (`VERIFY_TIMEOUT`). Set step `verify_timeout`
in the contract for slower suites, because two timeouts stop the mission as `no_progress`.
Checks must be safe to rerun and use the pinned mission workspace. JSON argv
arrays remain exact. Deterministic checks fail fast and cannot be overridden
by manual judgments. Verification runs in isolated process groups and cleans
up their remaining members; checks must not start persistent background work. Missing assessments leave the attempt active; assess and
verify again. Use read-only `diagnose` for recorded-fact failure routing; it authorizes no
retry. Change relevant tactics and retain evidence.
Context-based repeat detection is a heuristic, not proof of unchanged conditions.
Respect step/mission budgets and existing no-progress stops; never reset counters.
Distinguish progress, verified live waits, and no progress. Polling timeouts do not
prove execution failure. Retry only confirmed transient read/poll failures with
bounded backoff; never replay uncertain side effects. See
[continuation and observability](references/continuation-and-observability.md).
Use `handoff` for a concise checkpoint-derived transfer summary; revalidate
current state before continuing. For bug audits, apply [the review rubric](references/review-quality.md).

Use `block` only for an active step; `deny` applies to a presented approval request.
Resume invalidates completion, including downstream
steps; inspect interrupted external actions before any retry. Use
`start --revalidate` in dependency order to check prior work without executing
it again or consuming execution attempts. Never repeat external side effects
just because a session was interrupted.

Schema 3 records an atomic transition journal. Before retrying uncertain work,
use `recovery`, inspect both files and external outcomes, then `recover` with
the current report digest and an evidence-linked resolution. `completed` permits
checks-only revalidation; `not_applied` permits a budgeted attempt; `partial` or
`unknown` stays blocked. After a failed verification of reversible work with no
network access or external actions, use `applied_incorrect` to spend a budgeted corrective attempt;
do not record `not_applied` for work that did happen. Never infer completion from a changed file hash.

After step verification, use `coverage` and `criterion-review` with evidence
references and required `--evidence-kind` declarations. Use `evidence-audit` to
inspect proof-type gaps. Only explicitly supported, current criteria allow schema-3 finish;
unmet or unverified criteria do not pass. Changed outputs/inputs or revalidation
require fresh review. Keep revisions in separate directories; present the diff
and preserve the parent's frozen contract, evidence and budgets.

## Finish — Check the original goal before reporting success

After `finish`, re-read the ORIGINAL user goal and constraints, inspect the
combined artifacts, and verify that the completed steps together answer it.
Record the assessment with `goal-review --verdict pass|fail --rationale TEXT`,
citing artifact/check evidence and any remaining gap. Step completion alone is
insufficient. If the goal is unmet or uncertain, record `fail`, which changes
the outcome to `blocked`; explain the gap and escalate with a recovery proposal.
Do not silently report `done_verified`, weaken criteria, or override a stop.
`finish` sets `done_verified` before this review; `goal_review_status: missing` in
`status`, `handoff` and `diagnose` means the mission is not yet reportable as done.

Report the final label, verified step count, goal-review evidence, and unresolved
work. Existing labels remain unchanged. Manual review is an assessment, not an
automatic guarantee of semantic correctness.

## Learn — Compound evidence, not process

After each mission, write at most two reusable lessons to `.mission/lessons.md`
or the established shared store, using [the lessons template](templates/lessons.md).
On non-done exits add a brief retro: failure, weak/ambiguous criterion (or none),
and a concrete next-time improvement. Export `metrics` after goal review for a checkpoint/journal-derived exit snapshot;
retain it in `.mission/metrics.jsonl` deduplicated by exit_id. Unknown host usage
and human intervention counts stay null. See [the metrics template](templates/metrics-entry.json).

After every five distinct missions with exit records, review recurring lessons
in [skill learnings](references/skill-learnings.md). Promote only supported,
scoped corrections; future behavior changes require tests and a documented release bump.
See [workflow details](references/agentic-workflow.md) for counting and retention.

## Shared-store and observation reliability

Use `store-read`/`store-publish` for cooperative digest-checked publication of
shared lessons; merge conflicts instead of overwriting. Observe checkpoint/journal
size limits and preserve full histories before revisions. Optional `service-*`
helpers hold repeated failing safe observations and permit a bounded recovery
probe; they execute no requests and override no approval, recovery or budget.
Read [reliability details](references/reliability-patterns.md) for commands, limits
and the distinction between observations, permissions and verified outcomes.

For changes to this skill, compare the behavioral baseline as well as unit tests.
The CLI scenario suite is not a model-autonomy benchmark. Actual agent runs need
reviewed evidence. Reuse only scope/input/policy-bound derived analyses via the
optional cache helpers; a cache hit never replaces current verification or consent.

## Installation, paths and continuation

Implementation: install the complete `scripts/` directory and root `VERSION`; the CLI requires the adjacent `mission_control/` Python package.

Schema 3 may declare mission-level `allowed_paths` (e.g. `["out", "build"]`): when a contract declares allowed_paths, every step artifact path must stay inside it. Omitted or `["."]` permits the whole workspace. This validates declarations, not arbitrary commands; it does not create a sandbox. See [declared artifact containment](references/commands-helpers.md#declared-artifact-containment-schema-3).

Declare exact output paths in `effects.writes`. Files up to 1 MiB get SHA-256 receipts; larger files
and directories get weaker metadata receipts; a directory over 50,000 entries, a FIFO or a symlink cannot be
observed and needs a contract revision. Watched inputs stay exact-hash only, so a watched file over 1 MiB refuses to start.

Use one runtime root: `.mission/` by default. Keep contract/state, decision log, lessons and retained metrics together there. With an explicit `--mission PATH`, use PATH for every agent-written artifact and set `NO_PROGRESS_STATE=PATH/state/call_hashes.txt` for repeat history. Open legacy `mission/` only explicitly; do not automatically move or merge existing missions.

When continuation is unclear, read `handoff` or `diagnose`: inspect missing/unverified assessments, dependency blockers, selected mission directory and installation fingerprint. Suggestions grant no permission; respect stops, denials, recovery and budgets. A reported CLI path/fingerprint identifies the installed skill, not the Nestor UI mode.

Use `handoff --compact` for a small continuation summary; request the full report when omitted steps or approval/evidence details matter. Structural indexes are report-local; re-read live evidence and authorization before work.

## Reference map

Read only the file a task needs. Each one is linked from here directly.

| Need | Reference |
| --- | --- |
| Commands, contract format, checks, goal review | [lifecycle commands](references/commands-lifecycle.md) |
| Approvals, transitions, evidence, budgets | [approval and recovery commands](references/commands-approval-recovery.md) |
| Status, handoff, metrics, audits | [report commands](references/commands-reports.md) |
| Stores, service health, impact, cache, containment | [helper commands](references/commands-helpers.md) |
| Schema-3 evidence, recovery, effects, revisions | [evidence and recovery](references/evidence-recovery.md) |
| `discipline: strict`, `red`, `scope-note`, `gate`, pre-push hook | [strict discipline](references/strict-discipline.md) |
| Splitting steps, choosing tests, review in proportion to risk | [development method](references/development-method.md) |
| Starting safely before project changes | [controller activation](references/controller-activation.md) |
| Drafting, final review, lessons | [agent workflow](references/agentic-workflow.md) |
| Mission selection, briefs, decisions | [execution context](references/execution-context.md) |
| Progress, polling, retries | [continuation and observability](references/continuation-and-observability.md) |
| Limits, process cleanup, circuit breakers | [reliability patterns](references/reliability-patterns.md) |
| Evidence kinds, baselines, lesson audits | [quality and learning](references/quality-and-learning.md) |
| Bug audits | [review rubric](references/review-quality.md) |
| Promoting recurring lessons | [skill learnings](references/skill-learnings.md) |
| WSL paths and setup | [WSL guidance](references/wsl.md) |
| Design sources and limits | [research](references/research.md) |
| Recorded test results | [operational validation](references/operational-validation.md) |

Read [Nestor integration](references/nestor-integration.md) when installing or assessing host enforcement. The inspected Nestor build exposes no supported configurable pre-tool hook: no adapter/guard is installed. Shell writes remain outside enforcement; a hook alone would not prevent self-approval.
