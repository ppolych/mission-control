# Skill Learnings — Mission Control 0.4.2.10

This is the skill-level evidence register, separate from per-mission lessons.
No five-mission batch has been reviewed in this repository yet. Unit tests and
illustrative templates are not mission histories. No empirical budget tuning or
new check capability is claimed here.

## Review cadence and promotion

After each five distinct missions with exit/evidence records, review their latest
outcomes. Count resumed exits once. Promote a recurring correction only when at
least two distinct mission records support it, and retain its context and limits.
Read applicable promoted entries before drafting future contracts. See
workflow details (`references/agentic-workflow.md`) for lessons, metrics, and counting rules.

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

Behavior-changing releases need their own regression evidence and a release bump.
Operator-requested changes and engineering reviews are not mission evidence: never
count tests or review passes as completed missions or as measured safety gains.
Release history is in `CHANGELOG.md`, and test results are in `references/operational-validation.md`.
