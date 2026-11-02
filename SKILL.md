---
name: mission-control
description: Orchestrate goals with durable mission state, evidence-based verification, bounded recovery, and explicit outcomes. Use for substantial multi-step, controlled, autonomous, or multi-session work, and whenever the user asks for this skill by name, however small or urgent. Otherwise exclude simple edits and quick questions.
metadata:
  version: "0.4.2.6"
  author: "Panos Polychronis"
  email: "ppolych@netcompany.com"
---

# Mission Control

Version 0.4.2.6. Requires Python 3.11+, Bash, and Unix locking on Linux, WSL2,
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
Never delete the mission root. Report every refusal in your final message.
Follow [controller activation](references/controller-activation.md) for branching,
failures and proof. These are agent rules, not a
host enforcement hook.

When the user asks for this skill by name, a project change goes through a mission,
however small. Urgency does not waive this: use [the short path](#small-changes).
If you will not use the mission, say so and why before the first project change.

## Command path

Set `SKILL` to this skill's absolute directory. If the host gives a Windows path and Bash runs in WSL, use
`SKILL=$(wslpath -u 'C:\path\to\skill')`. Never search with `find /`. Every command takes `--mission PATH`
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

## Small changes

For one small change with a test, this is the flow; read nothing else unless a command refuses. Fill in
[the template](templates/small-fix-contract.json) outside the workspace. Use `test_first_exempt` only if no test can apply.

```bash
M="$SKILL/scripts/mission.py"
contract=$(mktemp)
python3 "$M" validate --contract "$contract"
python3 "$M" init --contract "$contract" --workspace "$PWD"
python3 "$M" start --step fix
python3 "$M" red --step fix
```

Write the edited template to `$contract` first, and any missing test before `red`. Make the change only now, then:

```bash
python3 "$M" verify --step fix
python3 "$M" criterion-review --criterion AC-1 --verdict supported --rationale TEXT --evidence-ref check:fix:0 --evidence-kind behavior
python3 "$M" finish
python3 "$M" goal-review --verdict pass --rationale TEXT
```

Record `supported` and `pass` only if results show it. For a requested push: commit,
run `python3 "$M" gate --commit SHA`, and push only on exit 0.

## Larger missions

For anything beyond one small change, read the [mission guide](references/mission-guide.md) first. Inspect the workspace,
then self-answer [the draft template](templates/draft-contract.md) and present a COMPLETE contract from
[the template](templates/contract.json); ask only for genuinely consequential missing requirements. Run `validate`, then
`init`. Never overwrite or weaken an existing contract: new requirements need `revision-diff`, then `revise` into a separate
destination. Existing schema-2 missions stay compatible. A strict mission stops before a push: keep the push out of the
steps, then after `finish` and a passing `goal-review` commit, run `gate --commit SHA`, and push only if it exits 0.

## Rules while running

Use `mode: controlled` for interactive/sensitive work and `autonomous` for sandboxed/CI work (the default). Neither creates a
sandbox, and both preserve host permissions.

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

Approvals bind to the contract and workspace digest. Denied steps stay blocked without automatic retry, including after resume.
`resume` from `human_abort` requires `--rationale` and the user's explicit request.

Checks must be safe to rerun; manual judgments cannot override them. Each has a 60-second limit (`VERIFY_TIMEOUT`, or step
`verify_timeout`), and two timeouts stop the mission as `no_progress`. Respect budgets and never reset counters. Never replay
uncertain side effects: use `recovery`, inspect files and external outcomes, then `recover`. `partial` or `unknown` stays blocked,
and `not_applied` must not be recorded for work that happened; for reversible local work that failed verification, use `applied_incorrect`. Only supported, current criteria allow schema-3 `finish`.

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

## After the mission

Write at most two reusable lessons to `.mission/lessons.md`, and export `metrics` after goal review. Unknown host usage and
human intervention counts stay null. Use one runtime root, `.mission/` by default; `handoff` and `diagnose` grant no permission.

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
| Drafting detail, running rules, lessons, stores, install paths | [mission guide](references/mission-guide.md) |
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
