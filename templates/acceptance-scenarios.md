# Acceptance scenario — <acceptance-id>

Draft alongside the contract, in its draft document or the selected mission's
`acceptance-scenarios.md`. This is a writing aid, not a new contract schema or an
automatic pass. Carry the observable requirement into the contract description
and its declared checks/manual rubric before initialization.

- **User outcome**: the original requirement this scenario tests.
- **GIVEN**: concrete preconditions, inputs and relevant constraints.
- **WHEN**: the user or system performs the relevant action.
- **THEN**: observable result, including a measurable boundary where relevant.
- **Negative case**: invalid input, failure or interrupted outcome, if meaningful.
- **Step IDs**: declared steps that contribute to this requirement.
- **Check index**: zero-based check positions and expected results; label shared checks.
- **Evidence**: behavioral test/output references; identify manual judgment explicitly.
- **Rerun safety**: why verification repeats safely without external side effects.
- **Remaining gap**: what is unsupported/unverified and how it will be resolved.

Example: GIVEN a temporary workspace and a contract permitting only `out`, WHEN
initialization declares `outside/result` as an output, THEN it exits 2, identifies
the containment violation and preserves any existing contract/checkpoint bytes.
The evidence is an isolated rejection/preservation test, not merely a file check.
