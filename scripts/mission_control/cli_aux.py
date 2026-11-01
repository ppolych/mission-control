"""CLI commands that do not operate on an initialized mission checkpoint."""
import hashlib
import json
import os
from pathlib import Path

REPEAT_LOCK_WAIT_SECONDS = 10


def run_repeat(arguments):
    from .storage import atomic, persistent_lock
    if not arguments:
        raise ValueError('repeat requires a subcommand')
    command, *args = arguments
    path = Path(os.environ.get('NO_PROGRESS_STATE', '.mission/state/call_hashes.txt'))
    threshold = int(os.environ.get('NO_PROGRESS_THRESHOLD', '2'))
    if threshold < 1:
        raise ValueError('threshold must be positive')
    def load():
        rows = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else []
        if not isinstance(rows, list):
            raise ValueError('invalid repeat history')
        return rows
    if command == 'history':
        print(json.dumps(load(), indent=2))
        return 0
    if command not in ('record', 'check', 'reset') or (command != 'reset' and not args):
        raise ValueError('expected record/check tool args')
    key = hashlib.sha256(json.dumps(args).encode()).hexdigest()
    if command == 'check':
        return int(load().count(key) >= threshold)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Parallel tool calls record together, so wait briefly instead of losing an entry.
    with persistent_lock(path.with_name(path.name + '.lock'), wait=REPEAT_LOCK_WAIT_SECONDS):
        if command == 'reset':
            atomic(path, [])
            return 0
        rows = load()
        rows.append(key)
        atomic(path, rows)
    return int(rows.count(key) >= threshold)


def run_migrate(args, root):
    from .publication import publish_migration
    from .validation import validate
    if not args.destination:
        raise ValueError('migration requires separate --destination')
    destination = Path(args.destination)
    if os.path.lexists(destination):
        raise ValueError('destination already exists')
    contract = json.loads((root / 'contract.json').read_text(encoding='utf-8-sig'))
    if not isinstance(contract, dict):
        raise ValueError('legacy contract must be object')
    if contract.get('schema_version') is not None:
        raise ValueError('migration accepts unversioned legacy contracts only')
    if 'features' in contract and 'steps' in contract:
        raise ValueError('ambiguous legacy step collections')
    legacy_steps = contract.get('features', contract.get('steps'))
    if not isinstance(legacy_steps, list) or not all(isinstance(step, dict) for step in legacy_steps):
        raise ValueError('invalid legacy steps')
    backups = {}
    for source in (root / 'contract.json', root / 'state/progress.json'):
        if source.exists():
            backups[source.name] = json.loads(source.read_text(encoding='utf-8-sig'))
    for step in legacy_steps:
        if 'verify' in step and 'steps' in step:
            raise ValueError('ambiguous legacy criteria')
        checks = step.get('verify', step.get('steps'))
        if not isinstance(checks, list) or not checks or not all(isinstance(item, str) and item.strip() for item in checks):
            raise ValueError('legacy criteria must be a nonempty string array')
        step['verify'] = [{'manual': item} for item in step.get('verify', step.get('steps', []))]
        step['legacy_passes'] = step.pop('passes', False)
    contract.pop('_usage', None)
    contract['steps'] = contract.pop('features', contract.get('steps'))
    contract['schema_version'] = 2
    validate(contract)
    publish_migration(destination, contract, backups)
    return 0


def run_helper(args, root):
    """Run a command needing no mission checkpoint; None means not a helper."""
    from .cache import analysis_cache
    from .impact import impact_report
    from .lessons import lessons_search
    from .quality import lesson_audit
    from .services import service_operation
    from .settings import MAX_SMALL_FILE_BYTES
    from .store import publish_store, read_bounded, store_snapshot
    command = args.command
    if command == 'lesson-audit':
        if not args.record:
            raise ValueError('--record required')
        record = json.loads(read_bounded(Path(args.record), MAX_SMALL_FILE_BYTES)[0].decode('utf-8-sig'))
        print(json.dumps(lesson_audit(record, args.as_of), indent=2))
        return 0
    if command in ('analysis-key', 'cache-save', 'cache-check'):
        report, code = analysis_cache(args)
        print(json.dumps(report, indent=2))
        return code
    if command == 'lessons-search':
        lessons_root = Path(args.lessons_root) if args.lessons_root else root
        print(json.dumps(lessons_search(lessons_root, args.query, args.limit, args.offset, args.diverse)))
        return 0
    if command in ('store-read', 'store-publish'):
        if not args.store:
            raise ValueError('--store required')
        if command == 'store-read':
            report = store_snapshot(Path(args.store))[0]
        else:
            if not args.content or not args.base_hash:
                raise ValueError('--content and --base-hash required')
            report = publish_store(Path(args.store), Path(args.content), args.base_hash)
        print(json.dumps(report))
        return 0
    if command.startswith('service-'):
        if not args.health_file or not args.service:
            raise ValueError('--health-file and --service required')
        if args.http_status is not None:
            if args.outcome or not 100 <= args.http_status <= 599:
                raise ValueError('use a valid HTTP status or outcome, not both')
            status = args.http_status
            args.outcome = ('success' if 200 <= status < 300
                            else 'transient' if status == 429 or status >= 500 else 'terminal')
        report = service_operation(Path(args.health_file), args.service, command[8:], args.outcome, args.retry_after)
        print(json.dumps(report))
        return int(command == 'service-probe' and not report['allowed'])
    if command == 'impact':
        if not args.source_root:
            raise ValueError('--source-root required')
        print(json.dumps(impact_report(Path(args.source_root), args.symbol), indent=2))
        return 0
    if command == 'migrate':
        return run_migrate(args, root)
    if command == 'validate':
        from .contract import validate_allowed_paths, validate_known_fields
        from .validation import validate
        contract = json.loads(Path(args.contract or root / 'contract.json').read_text(encoding='utf-8-sig'))
        validate(contract)
        validate_known_fields(contract)
        validate_allowed_paths(contract, Path.cwd())
        return 0
    return None
