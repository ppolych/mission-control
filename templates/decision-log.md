# Decision Log — <mission-name>

Proactive state externalization for a mission-control run. Copy this file to
`<workspace>/.mission/decision-log.md` at Phase 0 and keep it updated as the
mission makes judgment calls. Write an entry for every meaningful decision
(plan deviation, replan, rejected alternative, risky choice).

---

## Current Objective

- **Mission**: one sentence describing the goal.
- **Constraints**: what must be respected.
- **Budget**: attempts per step, no-progress threshold, iteration cap.

## Progress Summary

- **Completed**: what has been done and verified so far.
- **In progress**: the single step currently being worked on (at most one).
- **Next**: what comes next in dependency order.
- **Blocked**: anything waiting on a dependency or on the user.

## Decisions

### Decision: <short title>

- **Date**: YYYY-MM-DDTHH:MM:SSZ
- **Context**: what was true when this decision was made.
- **Decision**: what was chosen.
- **Rationale**: why this option won over the alternatives.
- **Alternatives considered**: at least one real alternative and why it was rejected.
- **Cost if wrong**: concrete consequence, affected requirement and reversibility.
- **Revisit when**: observable evidence that would change this decision.
- **Knowledge gaps**: what was unknown at the time, and any assumption made.

### Decision: <second title>

- **Date**: YYYY-MM-DDTHH:MM:SSZ
- **Context**: ...
- **Decision**: ...
- **Rationale**: ...
- **Cost if wrong**: ...
- **Revisit when**: ...
- **Alternatives considered**: ...
- **Cost if wrong**: concrete consequence, affected requirement and reversibility.
- **Revisit when**: observable evidence that would change this decision.
- **Knowledge gaps**: ...

## Knowledge Gaps

- What is not known yet that could affect the mission.
- What needs clarification from the user or a subject expert.
- Anything assumed in a decision that has not been verified.

## Draft and lesson provenance

- **Workspace evidence**: files/conventions used to draft the complete contract.
- **Relevant past lessons**: mission IDs and which acceptance criteria changed, or none.
- **Draft review**: amendments or existing authorization used to proceed.

## Goal Review and Exit

- **Original goal and constraints**: compare with the combined artifacts.
- **Holistic evidence / gap**: outcome beyond individual step passes.
- **Final label**: after goal-review when applicable.

## Non-done Retrospective

- **Failure**: concrete cause and evidence.
- **Weak or ambiguous criterion**: identify it, or state none.
- **Next-time change**: how a future contract or approach should differ.
- **Reusable lessons**: at most two in lessons.md, or none.

Record concise conclusions and source references, not private reasoning transcripts. A decision records judgment under existing authorization; it cannot amend a frozen contract, grant approval or clear a stop.
