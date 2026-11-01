# Commands: helpers

Stores, service health, code impact, the analysis cache, installation and declared artifact containment.

## Reliability helpers

- `store-read --store PATH`: report a bounded shared text store base hash/size.
- `store-publish --store PATH --content FILE --base-hash HASH`: cooperative
  conflict-aware publication; 2 on stale base/error, no forced overwrite.
- `lessons-search ... --diverse`: opt-in deterministic deduplication/Jaccard ranking.
- `service-status --health-file FILE --service NAME`: read advisory circuit status.
- `service-probe ...`: reserve a half-open safe-observation lease; 0 allowed,
  1 held, 2 invalid/error. No external request is made.
- `service-record ... --http-status N` or `--outcome success|transient|terminal`
  records the caller's actual observation, with optional `--retry-after SECONDS`.
- `impact --source-root PATH --symbol NAME`: read bounded Python AST/lexical
  impact and test candidates without importing project code or initializing state.
  Unread files appear in `skipped_files` and set `truncated`.

These commands do not modify the mission lifecycle. Store publication and health
updates write only the explicitly selected auxiliary files and persistent locks.
Read reliability semantics (`references/reliability-patterns.md`) for resource limits,
process-group cleanup, journal caps, ranking, probe timing and uncertainty.

## Analysis cache and lessons audit

- `analysis-key --source-root PATH --query TEXT --policy ID --input RELPATH`: build
  a derived-analysis scope fingerprint; repeat --query and --input when needed.
- `cache-save ... --cache FILE --report JSON --redacted`: explicit auxiliary
  cache publication. No frozen mission file may be used as the cache destination.
- `cache-check ... --cache FILE [--max-age 86400]`: reuse_allowed (0), refresh (1),
  invalid/error (2); never grants execution or substitutes verification evidence.

See semantics, formats and limits (`references/quality-and-learning.md`). The draft template
is supplemented by `templates/change-necessity.md`; no planning/approval gate is
added. `evals/run_behavioral.py` compares CLI scenarios separately from imported
agent-run reviews and refuses missing scenarios or incompatible baselines.

## Cache and evaluation safeguards

Known-full schema-3 journals refuse verification before any command runs.
Cache save/check perform postflight scope/input checks; detected drift cannot
publish or return a reusable report. Lesson dates accept absent/null as unknown,
but reject malformed falsey values and invalid explicit as-of timestamps.
The behavioral runner uses optimization-safe functional checks and atomically
publishes output without overwriting inputs/baselines/code (including aliases),
retaining existing report permissions.

## Modular installation

The CLI and wrappers require the complete `scripts/mission_control/` package beside `scripts/mission.py`, plus the skill-root `VERSION`. Commands, working-directory semantics and checkpoint formats are unchanged. Analysis cache engine bindings include every package Python source file; old bindings become stale.

Implementation responsibilities are separated into contract/validation, approvals, observations/coverage/recovery, storage/journal/publication, and operational-helper modules. `mission_control/cli.py` retains the central locked load and commit sequence, with transitions in the `lifecycle_*` modules. Imports between cooperating functions are explicit and resolved when called. Legacy fault injection uses a test-only adapter; the production entrypoint exports only `main`.

Cache publication refuses output or lock paths that alias declared inputs, the derived report, VERSION, the entrypoint or installed package sources (including existing hardlinks and resolved symlinks). Validation runs before lock creation and again before publication. This prevents observed alias overwrites; it is not a filesystem sandbox and cannot eliminate noncooperating path-replacement races.

## Declared artifact containment (schema 3)

Optional mission-level `"allowed_paths": ["out", "build"]` restricts declared artifacts to workspace-relative prefixes. When a contract declares allowed_paths, every step artifact path must stay inside it: `file`/`not_file`/`grep` check paths, `effects.reads`, `effects.writes` and `watch`. Prefixes match path components: `out/result` is allowed, `outside/result` is not. Prefix paths themselves are included.

Omitting the field preserves existing behavior. `["."]` permits the whole workspace. An explicitly declared list must be nonempty, contain unique nonblank strings and use relative paths without parent traversal; `.` is supported as the whole-workspace prefix. Declared artifact paths also reject absolute paths and parent traversal, even with `["."]`.

`validate` checks lexical containment and resolves paths against the caller's current workspace directory; run it from the intended workspace. `init --workspace PATH` resolves against that selected workspace before publishing the contract/checkpoint. Nonexistent artifacts are permitted, but resolved symlink escapes and unresolvable loops are rejected with exit 2 and an `escapes allowed_paths` diagnostic. A rejected initialization does not overwrite an existing contract.

This is declaration validation at validate/init, not a sandbox or ongoing filesystem monitor. It does not inspect shell strings or enforce access by `exec`, `exit0`, `test` or external tools. Symlinks can change after validation; existing observation/approval safeguards remain separate. Controlled/autonomous policy, recovery and journal formats are unchanged. Schema-2 lifecycle behavior is unchanged.

Containment compatibility: whole-workspace prefixes normalize `./` to `.`. Filesystem checks may name the workspace root (`file .`) when a whole-workspace prefix is allowed; a restricted prefix still rejects that root. `not_file` paths below regular files remain valid declarations: the check reports no directory entry. These cases do not relax absolute-path, traversal or symlink-escape rejection. Existing effects/watch path validation remains unchanged.

The default mission root is `.mission`, including repeat history `.mission/state/call_hashes.txt`. Write lessons, decision logs and retained metrics under the same selected root. For existing legacy data use `--mission mission`; no automatic move/merge occurs. If using an alternate root with the repeat wrapper, set `NO_PROGRESS_STATE=<selected-root>/state/call_hashes.txt`.
