# Nestor integration

## Installed loader

Inspected Nestor Desktop 2.0.3 on this machine. Its Electron main bundle resolves
`app.getPath("userData")`, appends `skills`, and exposes `skills:listSkills`,
`skills:installSkillFromZip`, `skills:installSkill` and `skills:updateSkill`.
Skill discovery reads SKILL.md from the installed skill directories.

On this Windows/WSL installation, the selected skill is:

```text
C:\Users\ppolych\AppData\Roaming\nestor-desktop\skills\mission-control
/mnt/c/Users/ppolych/AppData/Roaming/nestor-desktop/skills/mission-control
```

Install the whole package, including scripts/mission_control and root VERSION.
Retain a backup outside the skills folder, verify the embedded manifest, and
check the installed CLI. An existing conversation may retain earlier instructions;
reload the skill or start a fresh session. No session database edit is required.

## Pre-tool support finding

The inspected Electron bundle exposes skill management, but no configurable
pre-tool hook channel. The bundled Go backend has built-in sensitive-file policy
checks. Inspection found no exposed PreToolUse, preToolUse, hooks.json or equivalent
user hook contract. The before_tool substring belongs to pre_dirty_before_tool
tracking. Other hook references in the bundle belong to runtime instrumentation.
The upstream source repository was inaccessible; this finding is limited to the
installed build and discovered interfaces, not a claim about every Nestor version.
Documentation for other products named Nestor, Cursor or Claude is not evidence
of compatibility with this Desktop build.

No mission.py guard or Nestor adapter is added against an unverified interface.
The `gate` command and optional pre-push hook are host-independent checks on a commit; they
are not a Nestor adapter and stop nothing before a tool runs.
If a supported pre-tool interface becomes available, document its event schema,
path semantics, denial behavior and explicit enablement before implementing one.
It must remain disabled unless explicitly selected by the operator.

## Enforcement boundaries

Mission Control records/checks declared work; it does not sandbox tool execution.
Shell writes are not blocked by the skill. A future write-path hook would not by
itself intercept arbitrary shell effects, close filesystem races, or prevent an
agent from self-approving through a separate approval command. Existing host
permissions and the controlled-mode requirement for an actual user decision still
apply. Do not treat skill activation, a plan, or a hypothetical hook as authority.

## Real-session trials

Prepare new disposable cases with evals/nestor_trials.py. Preparation is not a
model run. Start each case in an independent Nestor session with Agent mode
explicitly selected, retain its real trace/model/settings and final state, and
have an operator review outcomes. Do not import or alter existing conversations.
Unknown intervention, attempt and recovery measurements remain null until observed.
