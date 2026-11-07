# Strict discipline

## Contents

- What each level guarantees
- Declaring it
- Step outcomes
- Test-first evidence
- Scope observation
- Commit gate
- Optional pre-push hook

Contracts with `"discipline": "strict"` get the rules below, and the template enables it.
Contracts without the field behave as before, and frozen contracts are never upgraded.

## What each level guarantees

| Level | Includes | What it means |
|---|---|---|
| Enforced by the controller | Refusals from `validate`, `red`, `verify` and `gate`, based on bytes, exit codes and recorded state | Applies only when the CLI is called. State is local and unkeyed, so this is no security boundary against an agent that edits it |
| Heuristic | Git observations, `failure_matches`, the list of trivially true checks | Evidence, not proof. False positives and negatives are possible |
| Agent statement | `--already-satisfied`, exemptions, `test-first-note`, `scope-note`, assessments | Recorded and shown in reports, never verified |
| Guidance | The development method reference, contract and result review | Depends on the agent following it; measure it with real trials |

Nothing here is a sandbox. An agent can drop the field in a new contract, skip the CLI or edit local state.

## Declaring it

```json
{"schema_version": 3, "discipline": "strict", "workspace_isolation": "shared"}
```

Each step that writes declares one of these:

```json
"test_first": {"command": ["python3", "-m", "unittest", "tests.test_x"],
               "failure_matches": "AssertionError",
               "test_paths": ["tests/test_x.py"]}
```

```json
"test_first_exempt": {"kind": "docs", "reason": "Wording only"}
```

Exemption kinds are `docs`, `config`, `exploratory`, `low_impact`, `not_reproducible` and
`not_applicable`. A small change needs only this one line.

**Manual-only exception.** A step with no automated check is accepted only when the step itself declares
`"manual_only": {"reason": "why no automated check is possible"}`. It cannot be supplied on the command
line. The result reads `manual_evidence_only: agent assessment, not automated verification`, with the
reason, in `verify`, `handoff` and `gate`. It never counts as automated verification and cannot support
`behavior` or `integration` evidence. A manual-only step without the exception is refused, and adding the
exception to a running mission needs `revise`.

`validate` also refuses a short list of always-true checks, such as `true`, `:`, `exit 0` and
`sh -c true`. That list is finite and says nothing about check quality.

`validate` also refuses a check that repeats an external action. When a step declares an external action, a
network effect or `reversible: false`, a check whose text exactly equals a declared action or command would
rerun on every `verify`, so check the result with a read-only command. This is an exact-text heuristic: a
reworded command is not detected, and frozen contracts are not rechecked.

New strict drafts also refuse an `exit0` check or `test_first` command whose program is a bare name not on
`PATH`, and a `watch` entry that is a directory or ends in `/`. Both would otherwise fail only at `verify`, after
the contract is frozen. A program a step creates needs a path such as `./bin/tool`. The `PATH` lookup runs where
`validate` runs, so a tool installed later is not seen.

After `revise`, the new mission keeps its parent's base and records the writes of every step a parent mission
started. A step redone with `--already-satisfied` then does not make `gate` refuse those files as work from
before the mission; files no mission in the chain started are still refused.

`test_paths` must be inside `effects.writes`, including an existing test the step should not change. Listing
it does not require a change: once `red` has run, `verify` refuses a test file that changed without a
`test-first-note`.

`effects.uncommitted` optionally lists declared writes that do not belong in a commit, such as generated
files. See the gate table.

## Step outcomes

`verify` refuses a step whose declared writes never changed from the baseline of its first attempt.
Checks-only revalidation is exempt.

When the requested state already exists, no artificial change is needed:

```bash
python3 "$SKILL/scripts/mission.py" verify --step STEP --already-satisfied --rationale TEXT
```

All checks must still pass. It is refused if a declared write did change. The outcome is recorded as
`no_change` with the rationale and is visible in reports. It is an agent statement: it can be misused, but
not invisibly.

`behavior` and `integration` evidence needs a `check:STEP:INDEX` reference to an automated check.

## Test-first evidence

Flow within one step: `start`, write the test, `red`, implement, `verify`.

`red` runs the declared command on the active step and spends no attempt. It records a nonzero exit, unless
the command timed out, died from a signal or returned 126 or 127. It stores the exit status, the match result
and digests of the test files, never the output. `failure_matches` is a heuristic: it shows the output
resembled what was expected, not that the intended assertion failed. Without it the record says `exit_only`.
A new function often fails with an import error, so the small-fix template omits it.

`verify` records `red_green`:

| Value | Meaning |
|---|---|
| `confirmed` | A red exists, test files are unchanged since it, and the implementation changed since it |
| `unconfirmed` | `test-first-note` recorded why that sequence could not hold |
| `not_applicable_no_change` | Outcome was `--already-satisfied` |

Handling a wrong or changed test never requires undoing work:

| Case | What to do |
|---|---|
| Test is wrong and implementation has not begun | Fix it and run `red` again; history is kept |
| Test legitimately changes after implementation began | `test-first-note --step STEP --reason TEXT`; result is `unconfirmed` |
| Implementation began before `red` | Same note; result is `unconfirmed` |
| Test-first turned out to be unsuitable | `revise` with an exemption |

Neither the controller nor these documents ask for a temporary reversion. For stronger evidence after a test
change, optionally run the new test against the starting state in a separate clean worktree.
`confirmed` does not show the test is good or independent of the implementation.

## Scope observation

Strict steps snapshot `git status` and HEAD at `start` and again before checks run, so files made by the
checks are not attributed to the work. Git shows that a path changed, not who changed it, so every observed
path keeps `ownership: unverified`.

| Situation | Recorded | `verify` |
|---|---|---|
| Default: changed path outside declared writes | `observed` with unverified ownership | Passes and reports it |
| Path was already dirty, or HEAD moved | Same, with the doubt named | Passes and reports it |
| Contract declares `workspace_isolation: dedicated` | Same | Refuses before checks; nothing is reverted |
| Outside git, git failed, over 1000 changed paths | `status: unavailable` with the reason | Passes and says the check was not performed |

`dedicated` is the operator's statement that nothing else uses this workspace, such as a separate worktree.
The refusal rests on that statement, not on proof about a process. Mission Control creates no worktrees.

`scope-note --path P --disposition mine|not_mine|unknown --rationale TEXT` records a statement, not proof.
It changes no file, verification or stop reason, and accepts only an observed path.

| Current | Event | New | Effect on `gate` |
|---|---|---|---|
| `open` | No note, or `unknown` | `open` | Does not pass |
| `open` | `not_mine` | `stated_not_mine` | Observation no longer blocks |
| `open` | `mine` | `stated_mine` | Observation no longer blocks; a committed path is still out of scope until `revise` |
| `stated_*` | `unknown` | `open` | Does not pass |
| `stated_*` | Path content changed after the note | `open` | Does not pass |
| Any | `revise` declaring the path | Removed from observations | Judged as a declared write |

The latest statement applies, and every note stays in history and the journal.

**Limits.** Ignored files, changes outside the workspace, and a write undone within the step are not seen.
Outside git nothing is observed. Repository configuration such as a clean filter can still run during
`git status`; `core.fsmonitor` is disabled, but this does not protect against a hostile repository.

## Commit gate

`gate --commit SHA` is read-only. Exit 0 needs all of:

1. `done_verified`, a passing goal review, current coverage and no open scope observation.
2. A completed scope check for every step.
3. Every declared write passes the artifact table.
4. The commit passes the range table.

Otherwise it exits 1 with a reason per item, so later changes or commits are never certified silently.
No mission exits 1. A corrupt checkpoint, an unknown commit or a missing base object exits 2.

**Scope unavailable.** When a step's scope check did not complete, the report says
`scope_check: {"status": "not_performed"}` with the step and reason, never `passed`. With `--commit` that is
exit 1. Without `--commit`, for example outside git, the result is `mission_state_only`, `certified` stays
false, and commit content and range are listed as not evaluated.

Receipts hold a sha256 only for regular files up to 1 MiB. A directory receipt is a metadata manifest, and a
large file keeps only size and times, so neither can prove content.

| Receipt | In the commit | Result | Passes |
|---|---|---|---|
| sha256 | Same content and executable bit | `content_match` | Yes |
| sha256 | Different; git filters or line endings can also cause this | `content_mismatch` | No |
| sha256 | Blob over the limit | `unverified_oversized` | No |
| Large-file metadata | Anything | `unverified_metadata_only` | No |
| Directory manifest | Anything | `unverified_directory` | No; declare files, or `uncommitted` |
| Absent | Absent | `deletion_match` | Yes |
| Absent | Present | `content_mismatch` | No |
| Present | Absent, untracked | `not_in_commit` | No |
| Present | Absent, ignored | `ignored_not_in_commit` | No |
| Any | Symlink or gitlink, including in a parent path; never followed | `unverified_symlink`, `unverified_gitlink` | No |
| Missing or unavailable | Anything | `missing_receipt` | No |
| Declared `uncommitted` | Absent | `out_of_commit_not_certified` | Yes, reported as not certified |
| Declared `uncommitted` | Present | `unexpected_in_commit` | No |

When several steps write a path, the latest receipt decides.

The range is judged from the base recorded at `init`. With `--remote-sha`, which the hook passes, `gate` also
refuses a push carrying the base or earlier commits, because that work predates the mission. Without the flag it
does not look at the remote, so a person or script running `gate --commit` alone does not get this check.

| Case | Behavior |
|---|---|
| Paths changed since the base | All must be declared writes, otherwise `outside_scope`. Never drop a needed file, such as `.gitignore`, to pass: report the result as not certified, or declare the path through `revise` |
| Base is not an ancestor, as after a rebase | `base_not_ancestor`, with no fallback to a merge base |
| Base object missing, as in a shallow clone | Exit 2 |
| No recorded base | `no_base` |
| A `no_change` step's write differs from the base, as for uncommitted work from before the mission | `no_change_step_changed_path` |
| With `--remote-sha`: the base is not on the remote | `commits_before_mission`, even for an old unrelated commit |
| With `--remote-sha`: that commit is not available locally | `remote_commit_unknown` |
| With `--remote-sha`: first push, with no remote-tracking refs | Allowed, except `no_change_step_changed_path`. Earlier commits cannot be told apart here |
| Repository had no commits at `init` | Compared with the empty tree |
| Merge commit | Same rule on the final tree; bringing in other paths is `outside_scope` |
| Annotated tag | Its commit is judged; a tag of anything else is `not_a_commit` |

A revision keeps its parent's base and unresolved observations.

**What it does not certify.** It does not rerun checks. It does not judge quality. A local mission does not
prove who wrote a commit: a commit by someone else with the same content in declared paths passes, because
content is certified, not authorship.

Keep the push outside the mission, because `gate` needs a finished mission: `finish`, `goal-review`, commit,
`gate --commit SHA`, then push only on exit 0. A commit made before `finish` can still pass, but a push inside
a step happens before anything can be gated.

## Optional pre-push hook

Copy `templates/pre-push-gate.sh` to `.git/hooks/pre-push` by hand, and set `MISSION_PY`, plus `MISSION_DIR` if
it is not `.mission`. It is never installed automatically. Every push in that repository then needs a matching
mission, so use it only where that is wanted.

| Case | Behavior |
|---|---|
| Several refs | Each is judged; one failure stops the whole push |
| New branch | Judged normally |
| Force push | The new commit is judged; a warning says replaced commits are not evaluated |
| Deleting a ref | Allowed with a message; there is no content to certify |

`--no-verify` or editing the hook bypasses it. It is not a sandbox. A server has no access to the local
`.mission` state or artifacts, so this does not work as a server-side hook; that would need a separate design
for publishing evidence.
