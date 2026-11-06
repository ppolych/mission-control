# Schema 3: evidence, recovery, effects and revisions

## Contents

- [1. Requirements mapped to evidence](#1-requirements-mapped-to-evidence)
- [2. Unverified is distinct from failure and support](#2-unverified-is-distinct-from-failure-and-support)
- [3. Recovery reports before uncertain retries](#3-recovery-reports-before-uncertain-retries)
- [4. Watched input identity and safe observations](#4-watched-input-identity-and-safe-observations)
- [5. Declared effects](#5-declared-effects)
- [6. Explicit linked revisions](#6-explicit-linked-revisions)
- [7. Transition journal committed with the checkpoint](#7-transition-journal-committed-with-the-checkpoint)
- [Resource-bound persistence and process cleanup](#resource-bound-persistence-and-process-cleanup)

Schema-2 contracts/checkpoints remain
supported without migration or new default approval gates. Use the supplied
schema-3 template for new missions. Never change the schema of a frozen mission
in place; use an explicitly reviewed revision instead.

## 1. Requirements mapped to evidence

The contract declares a nonempty `acceptance` array with `id` and `description`
items, plus optional `evidence_kinds`.
Each step's `acceptance_refs` names the requirements it serves. IDs are unique;
unknown references and requirements with no mapped step fail validation.
Housekeeping steps may have empty references. At most 128 requirements and 256
entries in each path/reference list are accepted.

After mapped steps complete, inspect the actual combined outcome and record:

```bash
python3 "$SKILL/scripts/mission.py" criterion-review --criterion AC-1 \
  --verdict supported --rationale 'Compared actual report with the original request' \
  --evidence-ref file:report.txt --evidence-ref check:example-001:1 --evidence-kind content
python3 "$SKILL/scripts/mission.py" coverage
```

`check:STEP:INDEX` must refer to a passed check of a mapped step; indexes are
zero-based. `file:PATH` must currently exist and be observable beneath the pinned
workspace, as a regular file, a larger file or a directory. Multiple `--evidence-ref` arguments are allowed. References
and rationale must not contain secrets. File contents are never stored here.

`supported` requires completed mapped steps and at least one valid evidence
reference. It records an agent/operator judgment with evidence, not mathematical
proof of behavior. A file's existence alone must not be treated as proof that
its contents satisfy the user. The post-finish original-goal review remains
required, including requirements accidentally omitted from the contract.

## 2. Unverified is distinct from failure and support

Criterion verdicts are `supported`, `unmet`, or `unverified`. Unmet review returns
1; supported/unverified recording returns 0, which means the record was saved,
not that an unverified criterion passed. Missing or stale reviews appear as
unverified in `coverage`. Schema-3 `finish` requires every step completed and
every requirement currently supported; otherwise it returns 2 without changes.

Reviews bind to the mapped steps' current evidence and observed declared outputs,
watched inputs and explicit file references. Resume/reverification or changed
artifacts invalidate that binding. Re-review after inspecting the new evidence.
Successful verification also stores `verified_artifacts` receipts for
declared outputs and watched inputs. Supported review requires those receipts to
match current observations: rerecording the judgment cannot re-bless old checks
after a file changes. Perform checks-only revalidation, and then review.

A later step often changes a file an earlier step declared, as when a project
grows step by step. That earlier step then has a stale receipt and `finish`
names it. Run `start --step ID --revalidate` on that step alone: it spends no
attempt and leaves the other steps completed. Assess its manual checks again
from what you inspect now, run `verify`, then record `criterion-review` again.
The same works after `finish`: it reopens the mission for that step alone and
archives the goal review, so run `finish` and `goal-review` again afterwards.
Do not narrow `writes`, start a new mission or `resume` the whole mission to get
around a stale receipt. Do not declare a whole project or build-output directory
as a write either: build tools change it on every run, so it never stays current.
Older schema-3 checkpoints remain readable, but declared-file evidence without
receipts needs that same revalidation; no attempts or counters are reset.
Even after finish, a passing `goal-review` rejects stale acceptance evidence;
an explicit failing goal review still records the gap and blocks the mission.

Manual checks also support `assess --verdict unverified`. Verification then
returns 2 before running any commands and leaves the attempt active. It neither
records a failed verification nor spends another attempt. Provide a justified
pass/fail assessment before verifying again. This explicit verdict is available
for schema 2 too; existing pass/fail behavior remains unchanged.

## 3. Recovery reports before uncertain retries

Each schema-3 step declares `retry: inspect` (default) or `safe`. An interrupted,
explicitly blocked, or unsuccessfully verified execution using `inspect` requires
reconciliation before another execution or revalidation can start. Completed
steps resumed for checks alone do not require repeating their work. Interrupted
revalidation likewise reruns only the already-declared safe checks.

```bash
python3 "$SKILL/scripts/mission.py" resume
python3 "$SKILL/scripts/mission.py" recovery --step example-001
```

Inspect current files AND external systems; then record the observed outcome:

```bash
python3 "$SKILL/scripts/mission.py" recover --step example-001 \
  --digest DIGEST_FROM_CURRENT_REPORT --resolution completed \
  --rationale 'Inspected the resulting artifact and confirmed the external outcome'
python3 "$SKILL/scripts/mission.py" start --step example-001 --revalidate
```

The read-only report includes baseline/current hashes and modes for declared
write paths, classifications `unchanged`, `changed` or `unavailable`, prior
verification evidence, and explicitly unknown external-action outcomes. Hashes
do not prove that a deploy, message, payment, or other external action occurred.
The helper cannot observe undeclared effects. Inspect them independently.

Resolution is an explicit recorded judgment tied to the current report digest:

- `completed`: allow checks-only revalidation, without marking the step complete.
- `not_applied`: allow a normal execution attempt within the existing budget.
- `applied_incorrect`: only when the latest attempt failed verification, allow a budgeted corrective
  attempt; refused when the step declares network access, external actions or
  irreversible effects, because the external result is unknown.
- `partial` or `unknown`: remain blocked for recovery; return 1, without retry.

Missing/stale digest or unavailable file observations reject resolved outcomes
with code 2. Decisions retain the report, rationale and digest in recovery history.
The report includes step status, revalidation eligibility and a reconciliation
sequence. Any recorded reconciliation invalidates a previously presented report,
including another partial/unknown decision with unchanged file hashes.
No resolution refunds attempts, runs work, rolls back files, or grants permission.
Do not guess an outcome to unblock a retry. User-denied steps cannot be recovered
through this path. An explicit stop must be resumed first.

`retry: safe` is the contract author's repeat-safety assertion, not automatic
idempotency detection. It is invalid with network access, external actions, or
irreversible effects. It does not bypass the established checks-only revalidation
rule, approvals, budgets, or host controls.

## 4. Watched input identity and safe observations

`watch: ["input.txt", "src/config.py"]` lists bounded file inputs whose current
state participates in a controlled approval digest. A changed input or mode
invalidates the approval. `start` presents a new request without spending an
attempt. An old pending decision is rejected if inputs changed. Verification
and manual assessment cannot reuse stale approval; inspect/recover prior work
before obtaining a new approval and revalidating it.

Approval requests and approval records retain input observations. Autonomous
mode does not add approval gates; it records input baselines for inspection and
uses watched inputs in acceptance-evidence freshness.

Observations are no-follow, regular-file-only, nonblocking, and limited to 1 MiB
per file. They store SHA-256 plus mode, `absent`, or an unavailable reason. Paths
must be relative, nonempty, and contain no parent traversal. Symlinks, FIFOs,
directories, over-limit files and files observed changing during a read cannot
serve as readable approval/recovery evidence. No file bytes are retained. These
preflights do not provide filesystem race isolation or a sandbox.

Declared writes and `file:` evidence refs are the exception for size and type. A larger
regular file gets `kind: metadata` (size, mtime, ctime, mode). A directory gets
`kind: directory`, a no-follow manifest of each entry's path, mode, size and mtime,
limited to 50,000 entries and 64 levels; reading stops at the limit. Both detect ordinary rebuilds but are weaker
than SHA-256: an edit preserving all recorded metadata goes unnoticed. Symlinks, FIFOs
and over-limit trees stay unavailable and need a contract revision. Watched inputs
always use exact hashes because they bind approvals.

All schema-3 verification and manual assessment checks validate the canonical
workspace, including ungated/autonomous steps. Before committing a successful
verification, the helper checks the workspace and current gated approval again.
If identity changed during the checks, code 2 leaves the checkpoint unchanged
and the step active. Some checks have already executed; inspect their effects
before recovery/revalidation rather than interpreting the refusal as no work ran.

## 5. Declared effects

Every schema-3 step requires exactly these `effects` fields:

```json
{
  "reads": ["input.txt"],
  "writes": ["report.txt"],
  "network": "none",
  "external_actions": [],
  "reversible": true
}
```

`network` is `none`, `self_hosted`, or `external`; `reversible` is a strict JSON
boolean. Read/write paths are workspace-relative file paths; include created
and deleted files in writes. An absent path is a valid observed state for those
operations. Directories and files over 1 MiB get weaker metadata receipts, described
above; nothing here backs them up. List external actions in plain, bounded, nonsecret descriptions.

The full effects object appears in the approval step snapshot and revision diff.
It describes intent; it does not restrict tools, detect every undeclared write,
configure network access, create a backup, or prove reversibility. Host permission
and isolation remain necessary. Changing effects/commands/scope requires a revision.

## 6. Explicit linked revisions

Draft the proposed schema-3 contract outside the existing mission. Inspect:

```bash
python3 "$SKILL/scripts/mission.py" revision-diff --contract .mission/revised-contract.json
```

After authorization for the changed scope:

```bash
python3 "$SKILL/scripts/mission.py" revise --contract .mission/revised-contract.json \
  --destination mission-r2 --reason 'User authorized the described scope change'
python3 "$SKILL/scripts/mission.py" init --mission mission-r2 --workspace "$PWD"
```

`revision-diff` reads the stored parent contract and shows top-level changes,
added/removed/changed steps, commands/effects and step order. It does not alter
the checkpoint. `revise` publishes a separate contract-only directory atomically
using the existing staged-publication/locking mechanism. Source missions remain
unchanged. Existing destinations are refused, including after a partial prior
publication: inspect what exists instead of overwriting it.

Generated `revision` metadata contains the parent contract/checkpoint hashes,
parent mission path, monotonic revision number, rationale, timestamp and diff.
Parent contract/checkpoint snapshots live in `lineage/`. No approvals or completed
statuses are transferred. Initialize the new directory explicitly, inspect prior
actions before reuse, and obtain any required step approvals. New counters belong
to the new revision; the parent's counters remain intact in the source and lineage.
Never use revisions to disguise denied work or silently reset exhausted budgets.
Do not put a hand-authored `revision` field in the proposed contract.

## 7. Transition journal committed with the checkpoint

Schema-3 checkpoints contain a `journal` array. Every committed lifecycle mutation
appends action, step, sequence, timestamp, previous-event hash and resulting-state
hash. Pending requests, refusals, recovery decisions, criterion reviews and budget
stops are included. State and event are written in the same atomic replacement;
there is no separately appended log that can get ahead of the checkpoint.

`history` prints committed events. Status, coverage, recovery and revision-diff are
read-only. Exit 2 and repeated refusals that change nothing leave state and journal
unchanged; a refusal that records a new stop or exhausted budget commits one event.
The chain and final state hash are checked before lifecycle operations; malformed
state is not silently repaired. Preserve a corrupted checkpoint for explicit
recovery. Atomic writes prevent partial JSON but do not promise protection from
hardware/filesystem failure after a successful replacement.

The journal diagnoses actual helper transitions, not every command an agent ran
between them. It is unkeyed local evidence: someone able to rewrite state can
rewrite its hashes too. It is not authenticated consent or a tamper-proof audit
service. History is retained; archive closed missions under workspace policy.
Schema-2 missions do not acquire a journal automatically and `history` shows an
empty event list for them. None of these features grants additional permissions.

Mission and migration/revision publication locks are opened without truncation,
without following the final symlink, and without blocking on special files.
Only regular lock files are accepted; persistent lock inodes are never unlinked.
Symlink/FIFO locks return an error without touching the checkpoint or link target.

## Resource-bound persistence and process cleanup

Checkpoint publication/loading share an 8 MiB cap; schema-3 journals accept at
most 10,000 events. An over-limit write leaves the last checkpoint intact. Preserve
original history before explicitly planning a linked revision; never truncate the
journal or reset counters to evade limits. Verification commands run in their
own process groups; normal exits and timeouts clean up remaining group members.
Escaped sessions and external actions still require independent inspection.
See reliability patterns (`references/reliability-patterns.md`) for detailed limits and recovery.

New acceptance items may optionally declare expected evidence_kinds.
Supported review must declare them with --evidence-kind; legacy items with no
requirements retain prior behavior. See quality-and-learning.md for sufficiency
audit and the limits of reviewer-supplied semantic labels.
