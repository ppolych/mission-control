# Subagents, the acceptance panel and counted tests

Read this when a mission uses subagents, declares `acceptance_panel`, or a check refuses because tests were
not counted. It holds the detail behind `SKILL.md`, whose rules still apply.

## Contents

- [Subagents in Nestor](#subagents-in-nestor)
- [Briefs](#briefs)
- [The acceptance panel](#the-acceptance-panel)
- [Counted tests](#counted-tests)
- [More checks and evidence](#more-checks-and-evidence)
- [Controller identity](#controller-identity)
- [What these records prove](#what-these-records-prove)

## Subagents in Nestor

Nestor's `subagent` tool takes `type`, `description` and `prompt`. An `explore` subagent (the default) has read-only
tools: read, grep, list_dir, read-only bash and web search. A `general` subagent can also write, edit and run bash, needs
Agent mode, and runs one at a time unless `at_once` is set. A subagent sees nothing of your conversation and cannot ask
questions, so its prompt must carry everything it needs. Only its final answer comes back to you.

Rules for a mission:

- Only you run `mission.py` commands that change state. A subagent may run read-only ones such as `status` or `coverage`.
- Run at most one `general` subagent at a time, and only for the active step: the mission has one active step.
- Give a subagent a `brief`, not your own conclusions. A reviewer told what you believe tends to agree with it.
- Use an `explore` subagent for long research. Your context then grows by its findings, not by everything it read,
  and a command that hangs stops only that subagent.

## Briefs

`brief --role ROLE` prints a complete prompt and changes nothing.

| Role | Use | Extra flags |
| --- | --- | --- |
| `researcher` | Facts from official documentation, specifications and upstream source, each with its source | `--query TOPIC` |
| `tester` | Tests for a step written from its criteria and sources, without opening its implementation | `--step ID` |
| `skeptic` | One vote: does the work satisfy every criterion? | none |
| `reviewer` | Bugs introduced by the work, by priority, as JSON | none |

The skeptic and reviewer briefs include the git diff since the mission began and the content of declared files that git
does not track yet, up to 60 KiB, and name the files they left out. Give each brief to its own subagent: separate
subagents vote independently, and Nestor runs subagents started together at the same time.

## The acceptance panel

A strict contract may declare:

```json
"acceptance_panel": {"mode": "observe", "skeptics": 3, "review": true}
```

`skeptics` is 1 to 5 (default 3) and `review` defaults to true. After every step is complete, save each subagent's
whole reply, verbatim and not summarized, under `.mission/replies/`, and record it. The mission root is outside the scope
check, so these files never count as undeclared changes; a reply saved elsewhere in the workspace would.

```bash
"$M" skeptic-record --content .mission/replies/skeptic-1.txt
"$M" review-record --content .mission/replies/review-1.txt
```

The controller reads the reply itself. A skeptic reply counts only by its last line, `VERDICT: NOT_REFUTED` or
`VERDICT: REFUTED - <gap>`; any other reply is inconclusive and never counts as passing. A review reply must hold the JSON
the brief asks for; otherwise it is inconclusive.

The panel is satisfied when the current work has at least `skeptics` votes, more than half of them `NOT_REFUTED`, and,
with `review`, a readable latest review with no finding of priority 0 or 1 at confidence 0.5 or more. A finding with an
unknown priority or confidence counts as blocking. Each record is bound to the content of all declared writes, so any
change after a vote makes it stale: fix what a refuting vote names, then ask again.

In `observe` mode, `goal-review --verdict pass` still succeeds and prints what the panel lacks. In `enforce` mode it is
refused until the panel is satisfied. Start with `observe`, and use `enforce` once refusals have proved accurate.

## Counted tests

A passing test command proves nothing if it ran no tests: `go test ./...` exits 0 with `[no test files]`, and a `-run`
or `-k` filter that matches nothing also passes. Verify therefore grades every check of a schema-3 mission:

- `inspection`: file, grep and similar checks show that something exists.
- `build_only`: it built or type-checked; for a test runner, it ran zero tests.
- `assertions_executed`: a test runner ran tests; the count is recorded.
- `unknown`: a test runner's summary could not be read. It never satisfies a `test_first` command.

The argv decides the tier and the output only refines it, so a `cat` or `echo` of a runner's summary never counts as
tests. Recognized runners: `go test`, `cargo test`, `pytest` and `python -m pytest`, `python -m unittest`, `npm`/`pnpm`/
`yarn`/`bun test`, `node --test`, `jest`, `vitest`, `mocha`, `cargo nextest`, `mvn test` and `dotnet test`. Each runner's
own summary is read, and another runner's summary line in the output is ignored. `npm test` and similar run a script the
project chose, so any JavaScript runner's summary is read there. Go counts tests with `-v` or `-json`; a `test_first`
command must use one of them. `go test -list`, `-c` and `-run '^$'` run no tests and grade `build_only`.

In a strict mission whose `status` records a `controller`, the `test_first` command of each step must reach
`assertions_executed`, or verify fails with the reason. Drafting refuses a `test_first` command that is not a recognized
runner, unless `test_first.uncounted_reason` explains why its tests cannot be counted; `finish` and `goal-review` then
print which steps were not counted, for the final report.

## More checks and evidence

- `["not_grep", "PATTERN", "path"]` passes when the pattern is absent, for a change that must leave no old call or
  parameter behind. A missing file is an error, never a pass.
- `--evidence-kind source` with `--evidence-ref source:https://…` records where an API fact comes from, such as an
  OpenAPI file or an upstream test. Use it with fixtures copied from that source, not with mocks written from memory.
- `init` and `revise` refuse a strict contract that still holds template text starting with `Replace with`.

## Controller identity

`init` records the controller's version and a fingerprint of its code. If the code changes during the mission, commands
that change state refuse. Never edit the skill to get past a refusal: report the refusal to the user. When the user
upgraded the skill on purpose, `controller-adopt --rationale TEXT` records who changed it and why, and work continues.

## What these records prove

The controller cannot tell whether a reply came from an independent subagent, whether a test was written without
reading the implementation, or whether a source says what the rationale claims. It records these as claims, as it
records criterion reviews. The controller fingerprint is a tripwire, not protection: whoever can edit the controller
can edit the check. Counted tests prove that tests ran and passed, not that they test the right thing.
