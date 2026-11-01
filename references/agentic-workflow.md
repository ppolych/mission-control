# Risk-aware execution, autonomous drafting, final review, and learning

## Contents

- [Select and honor the execution mode](#select-and-honor-the-execution-mode)
- [Workspace-first contract drafting](#workspace-first-contract-drafting)
- [Goal checks at contract time and after finish](#goal-checks-at-contract-time-and-after-finish)
- [Episodic lessons and light retrospectives](#episodic-lessons-and-light-retrospectives)
- [Exit metrics and handoff](#exit-metrics-and-handoff)
- [Skill-level improvement cycle](#skill-level-improvement-cycle)

## Select and honor the execution mode

Draft `mode: controlled` for interactive/sensitive work when the user wants
selective oversight; use autonomous for sandboxed/CI missions. Autonomous remains
the default for existing contracts. Set each step's `risk` and `needs_approval`;
setting the latter on every step provides full step-level oversight. Controlled
does not stop at every low/medium step automatically, and neither mode creates
isolation or grants authorization beyond the host.

For every gated step, draft the actual description/scope, exact work `commands`
argv arrays, and normal `verify` criteria before initialization. Empty commands
must be explicit `[]`; describe manual/file operations in the summary. The agent
uses the arrays as its reviewed work plan; the CLI does not execute them.

When `start` returns 3, pause before work. Present the complete emitted step,
workspace and digest, including commands and acceptance criteria, and wait for
an explicit user decision. Record `approve` or `deny` only after that decision;
never self-approve. Approval returns the step to pending; start it explicitly.
Waiting consumes no attempts. Independent ready work may continue while waiting
or after another step is denied, but nothing may satisfy a denied prerequisite.

Approval records survive resume for the same frozen contract/workspace digest.
Denied steps stay blocked for that revision and cannot be retried automatically;
do not reset counters, relabel risk, remove gates, or use resume to override a
refusal. Changed commands/scope/criteria require a new user-reviewed mission
revision. Revalidation runs only acceptance checks against prior work. Full
state transitions, return codes and the policy/enforcement boundary are in
the approval CLI reference (`references/commands-lifecycle.md`).

## Workspace-first contract drafting

Read only the relevant workspace sources: instructions, entrypoints, existing
outputs, tests, configuration, and conventions. Check existing mission state
before creating anything; do not restart or replace an active mission. Then
read applicable entries in local `.mission/lessons.md`, nearby known prior mission
records, or an established shared store. Do not invent a global store or search
unrelated workspaces. If none exists, proceed without lessons.

Use `templates/draft-contract.md` to answer five questions yourself:

1. What is the goal as the user will check it?
2. Which constraints apply, based on explicit instructions and repository facts?
3. What risky boundaries exist, and what is already authorized?
4. What observable criteria prove each step and the combined outcome?
5. Which checks can safely rerun without repeating external side effects?

Present one complete draft with source paths, assumptions, dependencies, and
verification criteria. Distinguish unknown business requirements from facts you
can discover. Bundle any consequential remaining question with the draft and a
proposed default; do not execute work depending on an unresolved requirement.
The user is the reviewer. Reviewability is not a new approval gate: existing
authorization permits ordinary work to continue. Step count never triggers approval;
controlled mode separately gates high-risk or explicitly marked steps.

Record which relevant lesson changed which criterion. Lessons are evidence,
not authority to override user instructions or permissions. Transfer only rules
whose context matches the current mission; do not cargo-cult past budgets.
Drafting notes belong outside the immutable contract. New missions use schema 3;
legacy schema 2 remains supported. Read evidence and recovery (`references/evidence-recovery.md`)
for acceptance mapping, explicit effects, watched inputs, retry reconciliation,
linked revisions and the atomic journal.

## Goal checks at contract time and after finish

Prefer a rerunnable integration check of the combined deliverable. Add it to an
existing step or use a final ordinary step such as:

```json
{
  "id": "goal-check",
  "description": "Combined deliverable satisfies the original goal and constraints",
  "depends_on": ["example-001"],
  "verify": [
    {"manual": "Compare the combined deliverable with every requested outcome; cite artifact and integration evidence, and identify omissions"}
  ]
}
```

For multiple branches, list all terminal prerequisite steps. Use actual criteria
for the domain, not merely file existence or a repetition of "all steps pass".
The supplied contract template includes a combined-outcome manual criterion;
adapt it to the goal. Use `assess` for manual step criteria as usual.

After successful `finish`, re-read the original request as well as `contract.mission`
and constraints. Inspect the outputs together: completeness, integration, usability,
and explicit exclusions. Check for requested outcomes omitted from the draft.
A contract-time goal check does not replace this final comparison. Run any needed
safe integration check; never redeploy or send messages as a verification action.

Record a concise, evidence-linked verdict:

```bash
python3 "$SKILL/scripts/mission.py" goal-review --verdict pass \
  --rationale 'Original goal and constraints satisfied; report.txt and the integration check provide the evidence'
```

If incomplete or uncertain, use `--verdict fail` with the specific gap. It returns
1 and changes `done_verified` to `blocked`, retaining all step evidence and budgets.
Report that failure rather than the earlier step-level success. Propose a new
mission revision if acceptance requirements were missing; never edit the frozen
contract to manufacture a pass. Existing non-success stop reasons cannot be
replaced by goal review. `resume` invalidates completion and archives any verdict.

The CLI records the agent's assessment; it does not inspect prose for truth.
For compatibility, legacy `finish` still sets step-level `done_verified` without
requiring goal-review metadata. Agents following this skill must complete the
review before reporting success. Existing contracts need no migration.

## Episodic lessons and light retrospectives

Use `templates/lessons.md` for `.mission/lessons.md`, or follow the existing shared
store's format. Assign each mission a stable ID based on its directory/goal;
resuming it does not create a new mission. Retain zero to two reusable lessons
per mission, updating existing entries on resume instead of appending duplicates.
Never overwrite lessons from other missions in a shared store. Exclude secrets.

Each lesson records context, observed failure/success, evidence, the reusable
correction, and an observable criterion for a future contract. Keep only lessons
that would change a future decision; zero lessons is valid. Do not fabricate
experience from hypothetical examples or treat unit tests as completed missions.

For a non-done exit, update a short retro in the decision log: what failed, which
criterion was weak or ambiguous (or explicitly none), and how a future contract
or approach would differ. Budget/permission failures do not automatically mean
acceptance criteria were weak. Preserve the original criteria and exit label.
An interruption that forbids further writes takes precedence; defer recordkeeping.

## Exit metrics and handoff

Use the read-only `metrics` helper after final goal review to derive attempts,
revalidations, committed action counts and exit transitions from authoritative
state. Explicit exports to metrics.jsonl should be deduplicated by exit_id. Unknown
host tokens and human intervention counts remain null. Schema-2 event counts
are unavailable. Do not sum cumulative resumed snapshots or treat step-level
finish as final holistic proof. Use `handoff` for session transfers and
`lessons-search` for source-linked historical retrieval before drafting.
See operational details (`references/continuation-and-observability.md`) and the corrected
metrics template. Lessons/retrospectives remain agent-written; metrics fields
are derived, not guessed by the agent.

## Skill-level improvement cycle

Follow `references/skill-learnings.md` after each batch of five distinct missions
with exit/evidence records, including unsuccessful ones. Read relevant existing
records only. Deduplicate resumed missions by ID and use their latest exit.
If fewer than five have been observed, retain candidates without claiming a batch.

A recurring issue needs evidence from at least two distinct missions. Summarize
budget mismatches, missing check capabilities, or recurring anti-patterns with
links and context. Separate observations from proposed fixes; do not automatically
increase budgets based on five anecdotes or weaken verification criteria.

Within authorized scope, fold supported guidance into the reference and link it
from the skill. Changes to behavior/defaults/code require meaningful regression
checks, documentation, and an explicit release bump in `VERSION`, skill metadata,
README, and version expectations. If this skill is read-only or changes exceed
scope, record a concrete proposal in the mission instead. Do not add an approval
gate for routine lessons or existing authorized improvements.
