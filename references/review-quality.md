# Evidence-based bug reviews

Use this rubric when asked to check Mission Control for bugs. Preserve user
scope and applicable repository invariants; do not manufacture a finding to fill
a review quota. Review the requested code/state surface, including existing bugs
when the user asks for a repository-wide audit.

A useful finding is discrete and actionable, meaningfully affects correctness,
security, performance or maintainability, and has a demonstrated trigger. State:

- The exact input, transition, environment or concurrency condition.
- The expected invariant and the observed result, with file/line or evidence refs.
- The concrete affected workflow and severity proportional to that impact.
- A minimal reproducer/regression and the narrow correction it supports.

Distinguish proven bugs from documented limits, intentional behavior, and
unmeasured risks. For suspected downstream effects, identify the affected path
rather than speculating. Reject a proposed finding when evidence contradicts it,
with an explanation. Do not expand a bug fix into unrelated hardening or style
changes. Add a failing isolated regression before changing CLI behavior, then
run relevant and full checks. Never reproduce failure against operator missions.

Deduplicate related findings and preserve the strongest evidence. Report what
was examined, what was confirmed/rejected, actual test results, and unresolved
limits. Repeated review passes need not produce new bugs. A green suite is evidence
for its covered invariants, not proof that every possible goal is satisfied.
