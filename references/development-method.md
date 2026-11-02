# Development method

This is guidance. Unless a rule in the strict discipline reference enforces it, the agent must choose to follow it.

## Split work into steps

Give each step one result a check can observe. Put discovery first when it changes the plan. End with the
project's whole test suite where one exists, because a passing new test does not show the rest still works.

## Choose the test approach for the task

| Work | Approach |
|---|---|
| Bug that can practically be reproduced | Regression test that fails meaningfully before the fix; `test_first` |
| Behavior change or new feature | Appropriate automated tests; `test_first` when a failing test first is practical |
| Documentation, configuration, exploration, low-impact change | `test_first_exempt` with a one-line reason; still declare suitable checks |
| Bug that cannot practically be reproduced | `test_first_exempt` with kind `not_reproducible`; say what evidence replaces it |

Test behavior a user or caller can observe. Do not write tests that merely mirror the implementation: a test
that restates the code passes whatever the code means. Before relying on a test, name the change that would
make it fail.

## Before a corrective retry

Find the cause before trying again. Read the failure, reproduce it, and change one thing at a time. A repeated
tactic with no new information is what `no_progress` exists to stop.

## Review in proportion to risk

Before `init`, ask what the contract still leaves unclear, and which failure no declared check would catch.

| Work | Who reviews |
|---|---|
| Small and low risk | No separate reviewer; answer those two questions yourself |
| Medium, or changes behavior | A fresh review of the contract, if the host offers one cheaply |
| `risk: high`, external actions, hard to undo | Fresh review of contract and result, using a subagent or new session |

If the host cannot give a fresh reader, say so to the user and record it. Do not call such a review independent.
Use [the review brief](../templates/review-brief.md). The controller cannot prove a reviewer's independence.
