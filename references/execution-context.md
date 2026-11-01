# Mission-bound execution context

Use this workflow for substantial work or interrupted sessions. Existing host
authorization, controlled-mode approvals, budgets and recovery rules still apply.

Read [controller activation](controller-activation.md) before project mutations:
skill loading alone does not initialize or start the controller.

## Select and restore one mission

Pin the absolute workspace and selected mission directory, `.mission/` by default,
when the task starts. Pass the selected root consistently to lifecycle commands,
notes and exports; bind repeat history to the same root with NO_PROGRESS_STATE
when using an alternate root. Restore its frozen contract and checkpoint first.

Do not pick a mission based on modification time or combine several tasks' plans.
Use the workspace's default `.mission/` when no alternate root is requested.
Other folders alone are not a reason to pause. Resolve identity before mutation
only when the request conflicts with that selection or leaves a real ambiguity. Inspect `handoff` or `diagnose` for current status and
installation identity. These reports do not know Nestor's UI mode.

A completed step's evidence and receipts remain authoritative only under their
existing freshness rules. Notes and prior summaries cannot establish completion.
Do not run resume merely to refresh context: it changes lifecycle state and can
require revalidation. Inspect the checkpoint first.

## Specify observable acceptance

Before initialization, map every requested outcome to acceptance IDs, contributing
steps, check indices and expected evidence. Write concrete GIVEN/WHEN/THEN
scenarios using the [scenario template](../templates/acceptance-scenarios.md).
Add negative or boundary cases where they materially test the requirement.

Keep scenarios focused on user-visible behavior. A declared path or existence
check is structural evidence, not proof of content or integration. Identify
manual judgments and shared checks explicitly. Do not infer a precise per-check
requirement mapping from a step's acceptance_refs alone.

Run contract validation and, after initialization, inspect `evidence-audit`'s
traceability before work. Its links expose declared relationships, including
support steps with no acceptance mapping; they do not create another approval
gate, reject legitimate support work or prove behavior. Investigate real gaps
against the full user goal rather than narrowing that goal.

## Keep a small active brief

Use [execution-brief.md](../templates/execution-brief.md) for the single active
step when useful. Include mission/contract identity, relevant requirements,
inputs/outputs, current evidence, lifecycle boundaries and one next action.
Refresh at step boundaries or handoff, not after every tool call. Re-read live
state after interruption; briefs can be stale. Keep durable history in the
checkpoint and decision log, rather than repeating the whole plan in each brief.

Continue authorized work without routine per-step check-ins. A context refresh
or a suggested action does not override a denial, stop, budget, uncertain external
outcome, or host permission. Use the existing recovery workflow when needed.

## Record decisions with consequences

Use the [decision log](../templates/decision-log.md) for consequential choices:
what was decided, supporting evidence, why, cost if wrong, and an observable
revisit trigger. Record conclusions rather than private reasoning transcripts.
Resolve routine implementation choices within the agreed scope and authorization;
ask only for genuinely consequential missing requirements or authority.

A ledger entry cannot edit a frozen contract, grant approval or authorize new
external effects. Changed requirements use the existing separate revision flow.

## Review the combined outcome

After individual checks, compare the combined deliverable with the original goal,
constraints and scenarios. Inspect behavioral and integration evidence where
relevant; passing isolated tasks does not establish the user outcome. Use the
existing acceptance reviews, finish and goal-review lifecycle. A real gap remains
explicitly unmet/unverified or produces a failed goal review; do not weaken
criteria to obtain a success label. Keep useful evidence and handoff context
under the selected mission root.
