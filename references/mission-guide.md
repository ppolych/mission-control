# Mission guide

Read this before a mission larger than one small change. It holds the detail behind `SKILL.md`, whose rules still apply.

## Contents

- [Draft a mission](#draft-a-mission)
- [Run a mission](#run-a-mission)
- [Learn from a mission](#learn-from-a-mission)
- [Shared stores and observations](#shared-stores-and-observations)
- [Installation and paths](#installation-and-paths)

## Draft a mission

Inspect the workspace FIRST: relevant source, conventions, tests, existing
artifacts, and constraints. Before drafting, read lessons from similar prior
missions and the applicable `references/skill-learnings.md`.
Turn relevant lessons into observable acceptance criteria, not extra ceremony.
Use `lessons-search` on a known store for bounded, source-linked retrieval;
recheck current sources before applying history. Use optional `--diverse` for
nonredundant results and `impact`/an available LSP to locate affected code and
tests before drafting. These are candidates, not correctness evidence. Audit
contradicted/stale lessons before reuse; justify refactors with
`templates/change-necessity.md`, preserving the full goal.

Self-answer the five questions in `templates/draft-contract.md`,
then present a COMPLETE draft contract with evidence, assumptions, dependencies,
and rerunnable checks. The user reviews, approves, or amends your draft; do not
make them co-author it through step-by-step questions. Ask only for genuinely
consequential missing requirements, alongside the otherwise complete draft.
Step count never creates a gate. Existing authorization permits ordinary work;
controlled-mode step gates below still require explicit approval.

Pin one selected mission directory and restore its checkpoint before creating
notes or acting after interruption; context refresh alone is not a reason to
resume. Draft concrete GIVEN/WHEN/THEN outcomes and map them to step/check evidence.
Use `references/execution-context.md` for mission selection,
small active-step briefs, consequence-aware decisions and combined-outcome review.

For a new mission, create a schema-3 contract from `templates/contract.json` and write the draft as
`.mission/draft-contract.json`, inside the selected mission root: hosts such as Nestor refuse file tools outside the
workspace, and `init` copies the draft to `contract.json`. Write a revision draft inside the current root too. Include a
criterion testing whether the combined outcome satisfies the original goal, or
an optional final `goal-check` step. Keep requirements separate from tactics.
Optionally declare evidence_kinds per acceptance item; the new template requires
content evidence. Use `references/quality-and-learning.md` for
behavioral baselines, sufficiency gaps, diagnosis, lesson audits and analysis cache.
Map acceptance IDs to steps; declare exact effects, watched inputs and retry
policy. The template sets `discipline: strict`: a step that writes declares
`test_first`, or `test_first_exempt` with a reason. Choose in proportion to the task
using the `references/development-method.md`; `references/strict-discipline.md`
states what is enforced, what is a heuristic and what is only an agent statement.
A strict mission stops before a push: keep the push out of the steps, then after `finish` and a passing
`goal-review` commit, run `gate --commit SHA`, and push only if it exits 0. Read `references/evidence-recovery.md`
when drafting, reconciling interruptions, or creating revisions.
A filled-in code step, for a Go project; checks are exact argv arrays whose first item is the check kind:

```json
{"id": "client", "description": "HTTP client with typed errors", "depends_on": ["scaffold"],
 "verify": [["exit0", "go", "test", "./..."]], "risk": "low", "needs_approval": false, "commands": [],
 "acceptance_refs": ["AC-1"], "watch": [], "retry": "inspect",
 "effects": {"reads": [], "writes": ["client/client.go", "client/client_test.go"], "network": "none",
             "external_actions": [], "reversible": true},
 "test_first": {"command": ["go", "test", "./..."], "test_paths": ["client/client_test.go"]}}
```

`network` is one of `none`, `self_hosted` or `external`. The `test_first` command must also appear as an
`exit0` check, and `test_paths` must be listed in `writes` next to at least one file that is not a test.
`watch` takes files, never directories. Name example configuration files without a `.env` suffix, such as
`env.example`: hosts such as Nestor refuse to write `*.env` files, and a declared name you cannot write
needs a whole revision.
For that new mission run `validate`, then `init`; existing contracts must not be overwritten or
weakened. New requirements need an explicit new mission revision (`revision-diff`, then
`revise` into a separate destination). Existing schema-2 missions stay compatible. Use helper
paths relative to this skill. Details: `references/agentic-workflow.md`
and `references/commands-lifecycle.md`.

## Run a mission

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
`references/commands-approval-recovery.md`.
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
`references/continuation-and-observability.md`.
Use `handoff` for a concise checkpoint-derived transfer summary; revalidate
current state before continuing. For bug audits, apply `references/review-quality.md`.

Create no project file before `start`, not even by `go mod init` or `npm init`; inspect versions read-only.
Put files that tests need to compile, such as `go.mod` or `package.json`, in a first step with `test_first_exempt`
(kind `config`), so later steps can record a real `red`.
Declare housekeeping files such as `.gitignore` as writes of the step that creates them, or `gate` will refuse them.
Leave mission setup out of the steps: the contract and checkpoint belong to the controller, `init`
refuses declared paths inside the mission directory, and checks should not run the controller.
Declare the files a step changes, not the whole project or build output. When a later step makes an
earlier receipt stale, revalidate that step alone, as `evidence-recovery.md` describes.
After `finish`, further project changes need a new mission or a revision; record manual verdicts only
from inspection in the current mission, never by copying an earlier one.

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

## Learn from a mission

After each mission, write at most two reusable lessons to `.mission/lessons.md`
or the established shared store, using `templates/lessons.md`.
On non-done exits add a brief retro: failure, weak/ambiguous criterion (or none),
and a concrete next-time improvement. Export `metrics` after goal review for a checkpoint/journal-derived exit snapshot;
retain it in `.mission/metrics.jsonl` deduplicated by exit_id. Unknown host usage
and human intervention counts stay null. See `templates/metrics-entry.json`.

After every five distinct missions with exit records, review recurring lessons
in `references/skill-learnings.md`. Promote only supported,
scoped corrections; future behavior changes require tests and a documented release bump.
See `references/agentic-workflow.md` for counting and retention.

## Shared stores and observations

Use `store-read`/`store-publish` for cooperative digest-checked publication of
shared lessons; merge conflicts instead of overwriting. Observe checkpoint/journal
size limits and preserve full histories before revisions. Optional `service-*`
helpers hold repeated failing safe observations and permit a bounded recovery
probe; they execute no requests and override no approval, recovery or budget.
Read `references/reliability-patterns.md` for commands, limits
and the distinction between observations, permissions and verified outcomes.

For changes to this skill, compare the behavioral baseline as well as unit tests.
The CLI scenario suite is not a model-autonomy benchmark. Actual agent runs need
reviewed evidence. Reuse only scope/input/policy-bound derived analyses via the
optional cache helpers; a cache hit never replaces current verification or consent.

## Installation and paths

Implementation: install the complete `scripts/` directory and root `VERSION`; the CLI requires the adjacent `mission_control/` Python package.

Schema 3 may declare mission-level `allowed_paths` (e.g. `["out", "build"]`): when a contract declares allowed_paths, every step artifact path must stay inside it. Omitted or `["."]` permits the whole workspace. This validates declarations, not arbitrary commands; it does not create a sandbox. See `references/commands-helpers.md`.

Declare exact output paths in `effects.writes`. Files up to 1 MiB get SHA-256 receipts; larger files
and directories get weaker metadata receipts; a directory over 50,000 entries, a FIFO or a symlink cannot be
observed and needs a contract revision. Watched inputs stay exact-hash only, so a watched file over 1 MiB refuses to start.

Use one runtime root: `.mission/` by default. Keep contract/state, decision log, lessons and retained metrics together there. With an explicit `--mission PATH`, use PATH for every agent-written artifact and set `NO_PROGRESS_STATE=PATH/state/call_hashes.txt` for repeat history. Open legacy `mission/` only explicitly; do not automatically move or merge existing missions.

When continuation is unclear, read `handoff` or `diagnose`: inspect missing/unverified assessments, dependency blockers, selected mission directory and installation fingerprint. Suggestions grant no permission; respect stops, denials, recovery and budgets. A reported CLI path/fingerprint identifies the installed skill, not the Nestor UI mode.

Use `handoff --compact` for a small continuation summary; request the full report when omitted steps or approval/evidence details matter. Structural indexes are report-local; re-read live evidence and authorization before work.
