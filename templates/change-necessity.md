# Change Necessity — <mission-id / proposed refactor>

Agent-authored drafting aid, not a score or approval gate. Use when proposing a
refactor or new abstraction that adds maintenance surface. The implementation
must satisfy the FULL authorized goal; do not narrow success to avoid work.

- **Goal served**: which requested outcome/invariant requires this change?
- **Observed trigger**: concrete defect, duplication blocking correctness, or
  maintenance/operational problem, with current source/evidence references.
- **Direct correction**: can a focused change fully satisfy the goal? Why/why not?
- **Incremental refactor alternative**: affected boundaries, callers, tests,
  compatibility and rollback/recovery implications.
- **Added surface**: new dependencies, configuration, persistent state or commands.
- **Decision**: implement a focused correction, perform a justified incremental
  refactor, or defer the unrelated proposal. Explain the evidence and tradeoff.
- **Validation**: observable acceptance criteria and meaningful regressions.

Style preference alone is not evidence that a refactor is necessary. Advisory
judgment cannot grant permission, override frozen scope or create a step-count gate.
