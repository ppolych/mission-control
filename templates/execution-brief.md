# Active execution brief

Write to the selected mission directory's `execution-brief.md` when a task is
complex or context may be lost. Refresh at a step boundary, interruption or
handoff; do not rewrite a large plan after every tool call. This brief is context,
not live evidence, approval or a replacement for the checkpoint.

- **Mission directory**: absolute selected path; default `<workspace>/.mission`.
- **Workspace**: canonical workspace from current checkpoint.
- **Contract hash**: current frozen contract identity.
- **Controller evidence**: successful status/handoff or init/start result, selected root,
  operation/exit status and journal head when available; skill loading alone is not proof.
- **Active step**: ID, current status and execution versus checks-only revalidation.
- **Requirement**: acceptance IDs and the relevant scenario.
- **Inputs/outputs**: only paths relevant to this step and applicable allowed_paths.
- **Current evidence**: check indices, receipts/report references and observed gaps.
- **Authorization/recovery**: current approval, denial, stop and recovery boundaries.
- **Expected result**: observable behavior and exact rerunnable checks from the contract.
- **Next action**: one action consistent with the current lifecycle state.
- **Recheck**: read the selected checkpoint and current evidence before acting;
  inspect `handoff`/`diagnose` when unclear. A changed identity makes this brief stale.

Do not copy secrets, long tool output or private reasoning into this file. Keep
past decisions in decision-log.md and verified progress in the checkpoint. A
context refresh does not refund attempts or permit repeating external effects.
