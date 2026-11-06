# Activate the controller before project changes

## Contents

- [1. Select and inspect](#1-select-and-inspect)
- [2. Continue an existing mission](#2-continue-an-existing-mission)
- [3. Bootstrap a new mission](#3-bootstrap-a-new-mission)
- [4. Reserve work before changing artifacts](#4-reserve-work-before-changing-artifacts)
- [5. Verify and retain observable controller evidence](#5-verify-and-retain-observable-controller-evidence)

Loading mission-control supplies instructions. It does not initialize a mission,
reserve an attempt or activate a step. For an authorized project-changing mission,
use the controller and its actual tool results before changing project artifacts.
Read-only investigation may proceed without creating a mission; honor explicit
read-only requests even when this skill has been loaded.

A user who names this skill has asked for a mission, whatever the size or urgency
of the change. If you will not use one, say so before the first project change.
This rule is an instruction: nothing in the controller can detect that it was skipped.

Never delete or recreate the mission root to get past a refusal, even when little was
recorded: that erases the journal, and nothing can detect it afterwards. Use the way
forward the refusal names, and report every refusal in the final message.

## 1. Select and inspect

Pin the canonical workspace, installed skill directory and one absolute mission
root, `<workspace>/.mission` by default. Look for contract.json and
state/progress.json under that selected root; a `draft-contract.json` alone means
no mission was initialized yet. Do not choose another root because
it is newer or create a competing mission for the same work.

Inspect existing entries before writing. A malformed, unreadable or mismatched
checkpoint is an error to diagnose, not an absent mission to overwrite. A symlink
or unexpected file type is not permission to replace data.

## 2. Continue an existing mission

If a checkpoint exists, use the selected root explicitly:

```bash
python3 "$SKILL/scripts/mission.py" status --mission "$MISSION"
python3 "$SKILL/scripts/mission.py" handoff --mission "$MISSION" --compact
```

Require successful tool results and check the frozen goal, workspace, contract
identity, active step and stop/recovery/approval state. If compact output omits
needed details, request full handoff. Notes and earlier statements are not proof.

Reuse a valid active step for its existing scope. Pending work needs start before
execution. Interrupted uncertain work needs existing recovery handling; completed
work needs revalidation only when the current lifecycle requires it. Reading a
checkpoint or refreshing context is not a reason to call resume. A stop, denial,
malformed state or scope conflict cannot be cleared by silently creating a new
mission. Changed requirements use the existing separate revision workflow.

## 3. Bootstrap a new mission

With no checkpoint, inspect the workspace and relevant lessons first. Draft the
complete schema-3 contract and observable criteria, then present the draft for
review. Proceed under existing authorization where sufficient; ask only for a
consequential missing requirement or authority. Do not add a step-count or routine
per-step approval gate.

Before project changes, run and inspect successful results:

```bash
python3 "$SKILL/scripts/mission.py" validate --contract "$DRAFT"
python3 "$SKILL/scripts/mission.py" init --mission "$MISSION" --contract "$DRAFT" --workspace "$WORKSPACE"
python3 "$SKILL/scripts/mission.py" handoff --mission "$MISSION" --compact
```

Run validate from the intended workspace. An existing contract without a checkpoint
may be an interrupted initialization: preserve it and use init's compatibility
checks; do not replace it with a different draft. Bootstrap may write the selected
mission's draft, contract, decision log and state metadata. This limited setup
exception does not authorize writing project source/configuration before start.
Do not fabricate a checkpoint or edit its counters to make initialization appear
successful. If the installed controller is unavailable, repair the installation
within authority or report the blocker; do not silently fall back to narrative-only
execution.

## 4. Reserve work before changing artifacts

```bash
python3 "$SKILL/scripts/mission.py" start --mission "$MISSION" --step "$STEP"
```

Project writes, edits, deletes, renames and shell mutations require a current
in_progress step covering the intended work. Require start exit 0, or a current
validated checkpoint showing that the matching attempt is already active. Exit 3
is an approval request, not permission to work; follow the controlled-mode flow.
Other failures must be handled without resetting budgets or bypassing denials.

Revalidation authorizes checks only, not replay of earlier external effects.
Preserve the single-active-step design and all host permissions. An explicit host
policy denial is not resolved by performing the same denied action through a
different tool or shell command; use an authorized host exception if available.

## 5. Verify and retain observable controller evidence

After work, inspect the actual output and record any required manual assessment
with a concrete rationale. Then verify the active step. Missing assessments need
completion on that attempt, not another start/resume or budget reset. Do not claim
step completion until verification succeeds and live state records completed.

In the optional execution brief, retain the selected mission/contract identity,
step ID, operation/result, journal head when available and current evidence refs.
Do not copy entire state or secret-bearing command output. If a result is lost or
uncertain, inspect status/handoff and existing recovery rules before repeating an
action; prose such as “using Mission Control” is never controller evidence.

Finish through the existing acceptance review, finish and goal-review lifecycle.
The combined deliverable must satisfy the original goal, not just a checklist.

These are agent workflow requirements. They do not add a state format, scheduler,
permission grant or host execution hook. Guaranteed prevention of tool mutations
outside this sequence requires integration in the host execution layer.
