# Mission Control

Version: see `VERSION` (`python3 scripts/mission.py --version`). Release history is in [the changelog](CHANGELOG.md).

Author: Panos Polychronis — [ppolych@netcompany.com](mailto:ppolych@netcompany.com)

An orchestration skill for substantial controlled or autonomous goals. It coordinates work, checks observable results and preserves evidence across sessions. It records and checks work: it does not execute declared work commands, create a sandbox, prove semantic correctness or guarantee exactly-once external effects.

## Layout

- `SKILL.md`: activation and workflow, with a map of every reference.
- `scripts/mission.py`: CLI entrypoint. Install the complete `scripts/` directory with root `VERSION`; the CLI needs the adjacent `mission_control/` package, which uses only the standard library.
- `scripts/*.sh`: verification and repeat-detection wrappers.
- `templates/`: contract, drafting questions, decision log, lessons and metrics formats.
- `references/`: detailed behavior, one file per topic.
- `tests/` and `evals/`: regression tests, behavioral probes, benchmark and mutation check.
- `AGENTS.md`: project rules and invariants for anyone changing this repository.

## Quick start

Requires Python 3.11+, Bash, and Linux/WSL2/macOS. From your workspace, prepare a schema-3
contract using the supplied template, replacing the example criteria with your
actual acceptance checks. Inspect the workspace and similar past lessons first;
self-answer the [draft questions](templates/draft-contract.md), then present a
complete draft for user review instead of a sequence of intake questions.
Step count creates no gate. Controlled-mode gated steps require explicit approval
in addition to existing host authorization. Set `SKILL` to this skill's absolute directory.

```bash
python3 "$SKILL/scripts/mission.py" validate --contract contract.json
python3 "$SKILL/scripts/mission.py" init --contract contract.json --workspace "$PWD"
python3 "$SKILL/scripts/mission.py" start --step example-001
```

Perform the requested work, inspect the actual artifact and record the template's manual criterion:

```bash
python3 "$SKILL/scripts/mission.py" assess --step example-001 --check 1 \
  --verdict pass --rationale 'report.txt covers the original goal and constraints; source comparison confirms accuracy'
python3 "$SKILL/scripts/mission.py" verify --step example-001
python3 "$SKILL/scripts/mission.py" criterion-review --criterion AC-1 \
  --verdict supported --rationale 'Inspected report against the original request' \
  --evidence-ref file:report.txt --evidence-ref check:example-001:1 --evidence-kind content
python3 "$SKILL/scripts/mission.py" finish
```

Re-read the original request and inspect the combined output before reporting done:

```bash
python3 "$SKILL/scripts/mission.py" goal-review --verdict pass \
  --rationale 'Combined report.txt outcome answers the original request; cited source and integration evidence agree'
```

Initialization pins the workspace for lifecycle checks; later caller directories
do not change it. Missing manual assessments leave the attempt active: run
`assess`, then `verify` again without another `start`.

Lifecycle commands always use the stored mission contract; `--contract` applies
only to initialization and validation. Retries retain prior manual rationale
in history while requiring fresh assessments.

Initialization preserves an identical destination contract and rejects a different
one. Retry a contract-only interrupted initialization with the same contract.
An exhausted step leaves independent ready work available; dependent steps still
wait for verified prerequisites.

## Modes

| Mode | Intended use | Skill approval policy |
| --- | --- | --- |
| `controlled` | Interactive or sensitive work | Pause before `risk: high` or `needs_approval: true` steps. |
| `autonomous` (default) | Sandboxed work | No additional skill approval gates. |

Neither mode grants host permissions, bypasses host approvals or creates a sandbox. A gated `start` returns 3 and prints an `awaiting_approval` request. Show it to the user and wait; the digest is not a credential or consent. Then record the decision:

```bash
python3 "$SKILL/scripts/mission.py" approve --step example-001 \
  --digest DIGEST_FROM_REQUEST --rationale 'User explicitly approved the displayed step'
python3 "$SKILL/scripts/mission.py" start --step example-001
```

After an explicit refusal, run `deny` with the same arguments instead (returns 1). See [approval and recovery](references/commands-approval-recovery.md).

## Guarantees and limits

- Schema-3 contracts map acceptance IDs to steps and require current supported reviews before `finish`. Schema-2 missions keep working, with no automatic migration.
- Verification receipts go stale when declared outputs or watched inputs change. Files over 1 MiB and directories get metadata receipts, which are weaker than SHA-256. Watched inputs stay exact-hash.
- `validate`, `init`, `revise` and `revision-diff` refuse unknown contract and step fields, so a misspelled `needs_approval` cannot remove a gate. Prefix comments with `_`.
- Step `verify_timeout` (up to 86400 seconds) overrides `VERIFY_TIMEOUT`, whose default is 60. Timeouts count as failures.
- After a failed verification of reversible work, `recover --resolution applied_incorrect` allows a budgeted corrective attempt. Uncertain outcomes stay blocked until reconciled.
- `finish` sets `done_verified` before the required goal review. `status`, `handoff` and `diagnose` report `goal_review_status` until it is recorded.
- A hash-linked transition journal commits atomically with each schema-3 checkpoint. It is unkeyed local evidence, not an authenticated audit log.
- Everything depends on the agent following the workflow. These prompts install no host hook, and reviews are recorded judgments.

Details: [evidence and recovery](references/evidence-recovery.md).

## Runtime layout

New missions use one hidden directory in the workspace:

```text
.mission/
  contract.json
  state/
    progress.json
    call_hashes.txt
  decision-log.md
  lessons.md
  metrics.jsonl
```

The CLI creates the contract, checkpoint and repeat state; the agent writes the rest only when needed. Open an old `mission/` directory explicitly with `--mission mission`; nothing is moved automatically. For another mission root, set `NO_PROGRESS_STATE` to that root's `state/call_hashes.txt`.

## Validation

There is no hosted CI. Run every check on each platform you use:

```bash
evals/check_all.sh
```

After changing safety code, also run `python3 evals/mutation_check.py`. Use `python3 evals/benchmark.py` before optimizing. Results are recorded in [the validation record](references/operational-validation.md).

The CLI behavioral probes are not a model benchmark. Actual agent behavior has not been measured; prepare real sessions with `python3 evals/nestor_trials.py prepare --output PATH` and follow [the trial protocol](evals/agent-scenarios.md).

## Packaging

```bash
python3 scripts/package_release.py
```

Pass `--output PATH` to choose another location. The build emits a reproducible ZIP with an embedded `MANIFEST.sha256` and a `.zip.sha256` sidecar, and runs extracted-install smoke checks before publishing. Verify the checksum before distribution, because an abrupt stop between replacements can leave a mixed pair.

## WSL2

Run with Linux Python inside your distribution. See [WSL setup](references/wsl.md).
