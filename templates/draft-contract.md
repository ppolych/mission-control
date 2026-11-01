# Mission Contract Draft — <mission-id>

Agent-authored before initialization. Inspect the workspace and relevant prior
lessons FIRST, self-answer these questions, then present the complete draft for
review. Do not ask the user to fill in this template. It is a drafting aid, not
a new CLI command, approval gate, or part of the frozen JSON schema.

## 1. What is the goal as the user will check it?

- Original request and observable combined outcome:
- Explicit exclusions:

## 2. Which constraints apply?

- Code-impact/LSP candidates and tests (confirm actual bindings):
- Workspace evidence (paths, conventions, existing artifacts/tests):
- User constraints and consequential assumptions:
- Relevant prior lessons and the criteria they change (or none found):

## 3. Which risky boundaries exist?

- External actions or irreversible effects:
- Existing authorization, host permissions, and any unresolved boundary:
- Mode: controlled for interactive/sensitive work, autonomous for sandbox/CI:
- Per-step risk, needs_approval, and exact planned command argv (or []):

## 4. Which observable criteria prove each step?

- Complete step list, dependencies, and acceptance criteria:
- Stable acceptance IDs and the steps/checks/artifacts supporting each:
- Combined-outcome criterion or final goal-check step:
- Any genuinely consequential missing requirement, with proposed default:

## 5. Which checks can safely rerun?

- Exact argv checks, manual rubrics, and evidence locations per step:
- Watched input paths, declared read/write effects, network/external effects:
- Inspect/safe retry policy and evidence needed to reconcile interrupted effects:
- Why checks are safe to repeat without external side effects:
- Workspace, budgets, recovery approach, and final holistic review:

## Complete draft contract

Include the filled schema-3 JSON contract here or link its reviewable draft. The user
approves or amends it; proceed under existing authorization where sufficient.

## Quality of the proposed change

- Expected evidence kinds per acceptance item; specify behavior/integration proof
  when file existence cannot establish the outcome.
- Applicable lesson audit status and contradictory/stale evidence.
- Refactor/new abstraction rationale using change-necessity.md when relevant.
- Any reused derived analysis: input/query/policy binding and current source check;
  no reused approvals or current-verification claims.


## Requirement-to-evidence map

For each acceptance ID, fill a concrete GIVEN/WHEN/THEN scenario using
[acceptance-scenarios.md](acceptance-scenarios.md). Include meaningful boundary
or negative cases where they affect the requested behavior. Map the scenario to
step IDs, zero-based check indices and expected evidence; explicitly identify
manual judgments or shared checks. A file-existence check alone does not prove
content or behavior. Resolve uncovered requirements before implementation without
weakening the original goal. After initialization, inspect `evidence-audit` for
structural links; its mapping is not a behavioral verdict.

## Execution context

Pin one absolute mission directory and workspace for this task. Restore that
mission's contract/checkpoint before creating notes; never select another mission
because its files are newer. If the intended mission is ambiguous, resolve its
identity before work. Maintain only the active step's small
[execution brief](execution-brief.md); record consequential decisions in the
selected mission's decision log with rationale, cost if wrong and revisit trigger.


## Controller activation path

- Selected absolute workspace and mission root:
- Existing checkpoint: restore status/handoff and the current attempt; draft only
  necessary separate revisions, not a competing mission.
- New mission or contract-only interrupted initialization: preserve existing data,
  validate the complete draft and initialize successfully before project changes.
- Selected step and successful start/current in_progress proof before mutations:
- Required assessment indices, real verification evidence and final goal review:

Existing authorization applies; this checklist adds no approval gate. Bootstrap
writes are limited to selected mission metadata, and read-only requests stay
read-only. Follow [controller activation](../references/controller-activation.md).
