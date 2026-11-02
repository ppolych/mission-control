# Changelog

Test results for each release are in [the validation record](references/operational-validation.md).

## 0.4.2.7

No behavior change. Removes a leftover line in `AGENTS.md` that contradicted bumping the version with every change.

## 0.4.2.6

No behavior change. Records the real Nestor run on 0.4.2.5, and every committed change now gets its own version, so an installed number identifies its content.

## 0.4.2.5

The host resends `SKILL.md` with every model call, so its size is paid for repeatedly on small tasks.

- `SKILL.md` shrinks from about 20 KB to about 11 KB. Drafting, running, learning, store and install detail moves to `references/mission-guide.md`, which a larger mission reads first. Activation, the short path, approval rules, recovery limits and the final goal review stay in `SKILL.md`.
- The effect on tokens has not been measured in a real session.

## 0.4.2.4

In a real Nestor session, `red` refused the import error of a new function against the small-fix template's `failure_matches`. The agent deleted `.mission`, started over and did not report it.

- The small-fix template no longer sets `failure_matches`, so that red records `exit_only`.
- The `red` refusal names the ways forward and says not to delete the mission directory.
- The skill forbids deleting the mission root and asks for every refusal in the final message. This is an instruction: nothing can detect a deleted mission afterwards.
- The `test_paths` refusal says that an existing test also belongs in `effects.writes`.

## 0.4.2.3

In a real Nestor session, an agent committed work with no mission, was stopped by the pre-push hook, then started a mission on that commit and recorded it as already satisfied. `gate` certified it and the push passed, without `--no-verify`.

- `gate --commit SHA --remote-sha SHA` refuses a push carrying the mission's base or earlier commits. The pre-push hook passes the flag, so existing copies of the hook need replacing. A first push, with no remote-tracking refs, cannot tell earlier commits apart.
- `gate --commit` refuses a path that a `no_change` step claims was already satisfied but that differs from the base, which covers uncommitted work from before the mission.

## 0.4.2.2

A real Nestor session under time pressure loaded the skill and then skipped the mission, citing the small size of the task.

- The description and activation rule say that a user naming the skill requires a mission however small or urgent, and that an agent declining must say so before the first project change. This is an instruction, not enforcement.
- New short path in `SKILL.md` and `templates/small-fix-contract.json`, tested from red to a certified commit, so one small change needs no further reading.
- The skill and WSL guide say to convert a Windows skill path with `wslpath` and never to search with `find /`, which took about 21 minutes on a real run.

## 0.4.2.1

Findings from real Nestor trials in strict missions.

- `validate` and new-contract `init` refuse a check that exactly repeats a step's external action or declared outside-effect command. Frozen contracts are not rechecked.
- After a passing goal review, the advisory note names `gate --commit SHA` before any push. The action and its argv are unchanged.
- The skill and strict discipline reference state that a push belongs outside the mission, and that `test_paths` stays inside `effects.writes`.

## 0.4.2

Add optional `discipline: strict` in schema 3, enabled in the template. Contracts without it keep their behavior, and frozen contracts are not upgraded.

- `verify` refuses a step whose declared writes never changed, and `--already-satisfied` records a valid no-change outcome.
- `red` and `test-first-note` record red/green evidence. A match is evidence, not proof, and nothing asks for work to be undone.
- Git-based observation of changes outside declared writes, with unverified ownership, and `scope-note` for recorded statements.
- Read-only `gate --commit` and an optional pre-push hook template. These are not a sandbox and do not show who wrote a commit.
- `manual_only` makes a step without automated checks explicit, and its result is labelled as agent assessment.
- New development method and strict discipline references, a review brief and strict trial cases.

## 0.4.1

- Report `next_action` in `status`, `handoff` and `diagnose`, and print it on stderr after transitions. It is advisory.
- State that an empty, dismissed or ambiguous reply is not approval, and that rationales use the user's words verbatim.

## 0.4.0

Changes since 0.3.3:

- Require Python 3.11. Refuse older versions with a clear message.
- Refuse unknown contract and step fields in new drafts.
- Add the `applied_incorrect` recovery resolution, based on the latest attempt only.
- Give larger declared outputs and directories metadata receipts instead of leaving steps stuck.
- Add step `verify_timeout`, and report the check index, exit status or timeout.
- Keep reports read-only and usable during `verify`. Only `init` creates a mission directory.
- Report `goal_review_status`, and require a rationale to resume `human_abort`.
- Report files skipped by `impact` and `lessons-search`. Serialize repeat records.
- Map unexpected exceptions to exit 2. Validate stored evidence and observation records.
- Refuse a mission root inside a declared output, and bound the stored contract read.
- Commit refusals only when state changes, and archive evidence at `start`.
- Sync directories after renames, and load modules only when needed.
- Make the shell wrappers executable. Split the command reference by topic.
- Add random lifecycle tests, a mutation check, a benchmark and `evals/check_all.sh`.

- Document the installed Nestor skill loader and the absence of a supported pre-tool hook; no speculative adapter is enabled.

## 0.3.3

Modular packaging and declared artifact containment. The CLI requires the complete `scripts/` directory and root `VERSION`. Optional schema-3 `allowed_paths` constrains declared paths at validate and init. Cache publication protects inputs, reports and installed files from output or lock aliases. Added compact handoff, structural traceability, continuation hints, reproducible packaging and Nestor trial preparation.

## 0.3.2

Quality, evidence and learning: a behavioral regression baseline, optional evidence kinds and `evidence-audit`, read-only `diagnose`, lesson validity audit, scope-bound analysis caching and a refactor-necessity template. A corrective review fixed full-journal verification, cache drift, malformed lesson dates, optimized-Python evaluation checks and report output collisions.

## 0.3.1

Bound supported reviews to verification-time receipts, invalidated old recovery reports after each reconciliation, validated ungated schema-3 workspaces and hardened lock opens. Added `metrics`, `handoff`, `lessons-search`, shared-store publication, process-group cleanup, state limits, optional diverse search, service circuit helpers and `impact`.

## 0.3

Schema 3: acceptance IDs mapped to steps, supported/unmet/unverified reviews, recovery reports before uncertain retries, watched inputs bound to approvals, declared effects, linked revisions and an atomic hash-linked journal. Schema 2 stayed supported.

## 0.2

Opt-in controlled mode with risk and approval flags, reviewable command declarations, digest-bound approvals and nonretrying denials. Autonomous stayed the default, on schema 2.
