# Commands: approval and recovery

## Contents

- [Controlled-mode approval policy](#controlled-mode-approval-policy)
- [Recovery and transition policy](#recovery-and-transition-policy)
- [Evidence and output](#evidence-and-output)
- [Per-step exhaustion and remaining work](#per-step-exhaustion-and-remaining-work)

Controlled-mode decisions, transitions, evidence and step budgets.

## Controlled-mode approval policy

A contract may set a mission-level `mode`. Omitted mode is `autonomous`;
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
