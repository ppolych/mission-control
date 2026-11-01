# Skill Learnings — Mission Control 0.3.3

This is the skill-level evidence register, separate from per-mission lessons.
No five-mission batch has been reviewed in this repository yet. Unit tests and
illustrative templates are not mission histories. No empirical budget tuning or
new check capability is claimed here.

## Review cadence and promotion

After each five distinct missions with exit/evidence records, review their latest
outcomes. Count resumed exits once. Promote a recurring correction only when at
least two distinct mission records support it, and retain its context and limits.
Read applicable promoted entries before drafting future contracts. See
[workflow details](agentic-workflow.md) for lessons, metrics, and counting rules.

Use this entry format when evidence exists:

- **Batch / distinct mission IDs**: references to the five reviewed missions.
- **Recurring observation**: observed pattern, supporting missions, and evidence.
- **Context and limits**: task classes where it applies and counterexamples.
- **Correction**: criterion/guidance change, or a scoped implementation proposal.
- **Validation**: meaningful regression or behavioral review and its outcome.
- **Disposition / release**: candidate, adopted guidance, or behavior change.

Preserve previous batches; mark unsupported candidates as rejected with reasons.
Do not raise budgets, add check types, or create universal rules solely to fill
an improvement quota. Keep entries short and evidence-linked.

## Release policy

Version 0.2 is an explicitly operator-requested behavior change, not an empirical
promotion from five mission histories. It adds opt-in controlled execution with
strict mode/risk/boolean validation, reviewable command declarations, digest-bound
approval records, and nonretrying user-denial blocks. Autonomous remains the
default and retains its existing workflow; contract schema stays at 2.

Validation on Linux/WSL2: the pre-change baseline was 76 passing tests. The
completed 0.2 suite passes all 104 tests (76 existing and 28 new), including
self-contained script copying and Unicode/space-path portability checks. Skill
validation, template validation, Bash syntax and ShellCheck also pass. New
isolated regressions cover gates, explicit decisions, resume, contract/workspace
binding, denial, invalid state/input, and autonomous compatibility. No completed production missions or measured safety improvement
are inferred from these tests. Future behavior-changing releases require their
own regression evidence and release bump.

## Version 0.2.1 — five-pass corrective review

Operator-requested review on 2026-10-30; these are five engineering passes, not
five observed production missions or evidence for budget tuning.

1. Transition review reproduced a denied retry mutating checkpoint state while
   independent work was active. Invalid active/dependency transitions now reject
   before denial handling, preserving checkpoint bytes.
2. Workspace review reproduced approval/start with a missing workspace and
   verification following a redirected symlink. Gated controlled approval,
   start, assessment and verification now validate the available canonical path.
   This does not establish filesystem race isolation or directory-inode identity.
3. Assessment review reproduced recording manual judgments with a missing/stale
   approval. Assessment now applies the same approval preflight as verification.
4. Checkpoint review reproduced silent regeneration of malformed pending
   requests. The complete snapshot and its digest are now validated before
   lifecycle mutation; invalid state remains unchanged for explicit recovery.
5. Compatibility review ran the complete suite and checked autonomous defaults,
   standalone script copying, migration/recovery, budgets, and Unicode paths.
   No additional defect was identified in this pass.

Validation: **111 tests pass** (76 original, 28 controlled-mode, 7 new regressions).
The new regressions were observed failing before their corresponding fixes.
Skill validation, contract-template validation, Bash syntax, ShellCheck and
documentation file-link checks also pass. The final test log is available for
this session at `/tmp/mission-control-five-pass-tests.log`.

## Version 0.3 — seven evidence and recovery capabilities

Explicitly operator-requested scope, not a promotion inferred from production
mission statistics. New schema-3 contracts add requirement-to-step acceptance
mapping, supported/unmet/unverified evidence reviews, digest-bound recovery
reconciliation, watched input identity, declared effects, linked immutable
revisions, and checkpoint-atomic transition history. The implementation remains
a self-contained standard-library Python script. Schema-2 missions retain their
existing lifecycle and autonomous approval defaults.

Regression coverage includes stale input/output evidence, no-follow bounded
observations, FIFO/oversize refusal, interrupted/partial effects, budget retention,
revision publication failures, lineage, journal integrity, and atomic write
failures. A disposable combined-flow smoke test covered approval, interruption,
recovery, checks-only revalidation, acceptance review, finish, goal review and
revision publication: one execution attempt, one revalidation, 13 committed
events, an unchanged parent checkpoint and no inherited child approvals.

These are tests, not completed operator missions or measured safety/performance
improvements. Effects are declarations, reconciliation and acceptance reviews
are explicit judgments, hashes are not authentication, and no sandbox or
exactly-once external execution guarantee is introduced. Details and command
semantics live in [evidence and recovery](evidence-recovery.md).

Final validation: **143 tests pass** (111 compatibility tests plus 32 schema-3
regressions), recorded in `/tmp/mission-v03-final-tests.log`. Skill/template
validation, Python syntax checks, Bash syntax, ShellCheck and documentation
file-link checks also pass. Runtime integration used a disposable workspace only.

## Version 0.3.1 — second five-pass corrective review

Operator-requested engineering review, not five production missions. All five
problem cases were reproduced with synthetic fixtures before their fixes:

1. **Acceptance freshness:** a changed output/input could receive a new supported
   judgment backed by old checks. Successful schema-3 verification now retains
   declared-file receipts; supported coverage requires current receipts. Existing
   schema-3 checkpoints without them remain readable and use checks-only
   revalidation to establish evidence without resetting counters.
2. **Recovery replay:** a report could be reused after another reconciliation
   when file hashes had not changed. Status, revalidation eligibility and a
   reconciliation sequence now participate in the report digest.
3. **Ungated workspace identity:** schema-3 assessment/verification could follow
   a redirected workspace unless the step required approval. Canonical workspace
   checks now cover all schema-3 steps, without adding autonomous approval gates.
4. **Lock-file integrity:** opening a mission lock in write mode truncated its
   contents and followed symlinks; special files could block. Mission and
   publication locks now use shared nontruncating, no-follow, nonblocking regular
   file handling while preserving persistent lock inodes and contention checks.
5. **Verification postflight:** watched inputs changing during checks could still
   complete an approved step. Successful schema-3 verification rechecks workspace
   and gated approval before committing. Refusal leaves the checkpoint active and
   unchanged, but checks have already run and their effects require inspection.

Validation: **154 tests pass** (143 prior plus 11 new) in the full suite, recorded
at `/tmp/mission-v031-full-tests.log`. Skill/template validation, Python syntax,
Bash syntax, ShellCheck and documentation file-link checks also pass. No operator
missions, external systems, or Daedalus sources were used as mutation fixtures.
These pre/postflights do not provide race isolation, sandbox enforcement,
authenticated consent, or an automatic proof of semantic correctness.

## Version 0.3.2 — requested quality and learning additions

Authorized release order: behavioral baseline → evidence sufficiency → diagnosis
→ lesson validity → derived-analysis reuse → refactor necessity. These additions
were explicitly requested, not promoted from invented five-mission histories.
Existing 0.3.1 lifecycle, approval, recovery and resource guarantees remain.
The CLI baseline observed on 0.3.1 passed 6/6 and the comparison passed 6/6; this
is control-plane conformance, not proof of improved autonomous model behavior.
Actual model runs require the separate agent-review protocol and artifacts.
New optional evidence kinds strengthen opted-in contracts; no existing mission
is upgraded in place. See quality-and-learning.md and the release validation record.

## 0.3.2 corrective review — reproduced code defects

Five review passes established capacity preflight, cache postflight freshness,
strict optional date typing, optimization-safe evaluation invariants and
alias-safe atomic report publication. These are regression-backed corrections,
not a five-mission empirical lesson batch. Preserve report permissions when
replacing previous non-atomic writes. Final evidence: 206 passing tests and
normal/optimized CLI probes 6/6; see operational-validation.md.

## Modular layout at unchanged 0.3.2

The historical single-file packaging described above has been replaced by a standard-library package beside the unchanged CLI entrypoint. Copy the complete scripts directory and VERSION. Every Python source/test file is capped at 400 physical lines; cache identity includes all package sources.


## Version 0.3.3 — release consolidation

The author requested this release bump after modularization, cache alias protection and restored allowed_paths validation with compatibility fixes. Keep the adjacent package installation requirement, 400-line Python cap and declaration-only containment explicit. Preserve historical test/evaluation provenance rather than relabeling old artifacts. No contract-schema, authorization, recovery or journal migration accompanies the release bump.
