# Reliability patterns

## Contents

- [1. Verification process groups](#1-verification-process-groups)
- [2. Conflict-aware shared lesson publication](#2-conflict-aware-shared-lesson-publication)
- [3. Bounded checkpoints and journals](#3-bounded-checkpoints-and-journals)
- [4. Optional diverse lesson results](#4-optional-diverse-lesson-results)
- [5. Advisory circuit breaker for safe service observations](#5-advisory-circuit-breaker-for-safe-service-observations)
- [6. Bounded code-impact candidates for contract drafting](#6-bounded-code-impact-candidates-for-contract-drafting)

Implemented as a standard-library Python package plus agent guidance. Install the complete scripts directory with the root VERSION file.
The current release is 0.4.2.10; these underlying policies are unchanged.
Contracts, approvals, recovery reports, mission modes and counters keep their
existing semantics. No Rust runtime, embedding service, network client or
background scheduler is introduced.

## 1. Verification process groups

Every verification subprocess starts a new POSIX session/process group, with
stdin from the null device. On timeout, the controller sends SIGTERM, allows up
to 0.2 seconds for its leader to exit, then SIGKILLs remaining group members and
reaps the leader. Normal completion also kills leftover group members: a check
must be synchronous and must not leave background work running. Declared work
commands remain agent-executed, not automatically launched by this helper.

Timeout evidence remains code 2, error_type timeout and null command exit status.
Normal command return status remains preserved. Descendants deliberately escaping
the group/session, privileged processes, external jobs and hardware failures are
outside this cleanup boundary. This is cleanup, not sandboxing or exactly-once
external execution. Interrupted/failed work still needs the normal recovery flow.

## 2. Conflict-aware shared lesson publication

```bash
python3 "$SKILL/scripts/mission.py" store-read --store /known/shared/lessons.md
```

Read the actual text, prepare an independently reviewed merged proposal file.

```bash
python3 "$SKILL/scripts/mission.py" store-publish \
  --store /known/shared/lessons.md --content /tmp/proposed-lessons.md \
  --base-hash HASH_FROM_STORE_READ
```

`store-read` is read-only and emits a digest and byte count, not file content.
The digest binds bytes and file mode. A missing file returns base_hash `absent`.
Both input texts are bounded UTF-8 (optional BOM), regular, no-follow files up to
64 KiB. `store-publish` locks a persistent sibling inode, checks the base twice,
stages/fsyncs the proposal and atomically replaces the destination. Existing mode
is preserved; a new store uses private temporary-file mode. A changed base returns
2 without replacing it; reread and merge the other edit rather than forcing it.

Only cooperating writers share the lock. Arbitrary external editors can still
race between the final observation and rename; this is not filesystem-wide
isolation or a permission grant. Keep secrets out of proposed lessons. Never
use this helper to modify frozen contracts/checkpoints. Persistent lock files
must not be removed. Retain the established maximum two lessons per mission.

## 3. Bounded checkpoints and journals

Checkpoint load and publication use the same 8 MiB serialized JSON cap. Reads
are bounded, no-follow and nonblocking regular-file reads; oversized, changing,
FIFO and symlink checkpoint entries are rejected, never silently repaired.
Schema-3 journals allow at most 10,000 events. Commit refuses an event beyond
that limit before writing a new checkpoint. Verification preflights known-full
journal capacity before running checks, refusing without side effects or state
mutation. Other byte-cap failures can still occur after checks produce evidence. A state write over the byte cap
leaves the previous checkpoint intact. Limits are fixed code constants, not
agent-controlled budget resets.

Preserve a full mission before planning a separate linked revision. Existing
oversized histories require explicit offline archival/inspection; do not truncate
or rewrite a frozen journal to evade the guard. A rejected commit after checks
may mean checks already executed; inspect outcomes before retrying. These guards
bound storage/read costs, not every computation or filesystem race.

## 4. Optional diverse lesson results

Add `--diverse` to `lessons-search` to remove identical case-folded/trimmed snippets
and greedily balance query relevance with token-Jaccard redundancy. It uses no
embeddings. Source path/line references remain present, tie order is deterministic,
and pagination is applied after ranking. Ranking examines at most the first 128
unique bounded candidates; the report marks truncation when that candidate budget
is exceeded. Default search ordering and all existing scan limits are unchanged.

Pages refer to the same observed store, not immutable snapshots. If source files
change between queries, restart retrieval and inspect the actual source. Diverse
ranking improves coverage of historical hints, not evidence of current behavior.

## 5. Advisory circuit breaker for safe service observations

Use only for already-authorized, repeat-safe reads/polls. These commands never
perform HTTP requests, refresh credentials, retry work, or grant approvals:

```bash
python3 "$SKILL/scripts/mission.py" service-status \
  --health-file /known/state/observations.json --service api
python3 "$SKILL/scripts/mission.py" service-probe \
  --health-file /known/state/observations.json --service api
```

Perform at most the permitted safe observation using the owning tool.

```bash
python3 "$SKILL/scripts/mission.py" service-record \
  --health-file /known/state/observations.json --service api --http-status 503
```

`service-status` is read-only. `service-probe` returns 0 when an observation is
allowed and 1 when held; neither value is permission for external work. Record
a current observation with `--http-status` OR `--outcome success|transient|terminal`.
HTTP 2xx is success; 429/5xx is transient; other statuses are terminal. Do not
infer HTTP status from arbitrary command exit codes. Authentication failures do
not trigger automatic credential refresh. A terminal record stays held until a
real observed success is explicitly recorded.

Three transient failures in a 60-second window open the breaker for 30 seconds.
`--retry-after SECONDS` extends that hold when longer; it never shortens server
advice. After cooldown, one half-open probe gets a 10-second lease under the
health-file lock; other probes wait. A successful observation resets failures;
a failed probe reopens the circuit. A lost probe can be claimed after lease
expiry. Closed-state observations are not serialized. There is no scheduler.

The health file is separate advisory state, not the mission checkpoint. Records
are atomic and locked; reads are bounded to 1 MiB and at most 128 services, with
strict timing validation. Outcomes are caller-reported, not authenticated; wall
clock changes can affect deadlines. Keep the file outside frozen mission state.
Inspect external outcomes after any ambiguity. Mission budgets, denials and
`retry: inspect` remain authoritative and cannot be bypassed by this helper.

## 6. Bounded code-impact candidates for contract drafting

```bash
python3 "$SKILL/scripts/mission.py" impact \
  --source-root /known/project --symbol save
```

Read-only, usable before mission initialization. Returns source path/line
references for Python AST definitions and call shapes, lexical symbol references,
and test-file candidates. It never imports or executes project code. Other
supported suffixes (`.rs`, `.js`, `.ts`, `.tsx`, `.go`, `.java`, `.cs`) receive
lexical references, not semantic parsing. Use the project's LSP/go-to-references
when available to resolve aliases, dynamic calls and actual bindings.

Traversal skips hidden/dependency directories and symlinks, visits at most 64
directories/64 files, and reads regular files up to 64 KiB using no-follow,
nonblocking reads. Results are capped at 256 per category. It can miss dynamic,
unsupported, large, generated or out-of-scope code and can match unrelated names.
Use candidates to draft effects/watch/test coverage, then verify actual behavior;
absence of a hit is not proof of no impact. This is not a full codebase graph.
