import contextlib
import json
import os
from pathlib import Path
from .settings import VERSION, MAX_STATE_BYTES

READ_ONLY_COMMANDS = ('status', 'history', 'metrics', 'handoff', 'coverage', 'recovery',
                      'diagnose', 'evidence-audit', 'revision-diff')
STEP_COMMANDS = ('start', 'verify', 'block', 'assess', 'approve', 'deny', 'recovery', 'recover')


def run_report(contract, state, args, root):
    """Print one report that never mutates mission state."""
    from .approvals import validate_approval_workspace
    from .contract import validate_known_fields
    from .coverage import coverage_report
    from .quality import diagnose_report, evidence_audit
    from .recovery import recovery_report
    from .reports import goal_review_status, handoff_report, metrics_report
    from .revisions import revision_diff
    from .transitions import find_step
    from .validation import validate
    command = args.command
    if command == 'evidence-audit':
        validate_approval_workspace(state)
        report = evidence_audit(contract, state)
    elif command == 'diagnose':
        report = diagnose_report(contract, state)
        report['mission_directory'] = str(root.resolve())
        report['goal_review_status'] = goal_review_status(state)
    elif command == 'metrics':
        print(json.dumps(metrics_report(contract, state, root)))
        return 0
    elif command == 'handoff':
        report = handoff_report(contract, state, root)
        if args.compact:
            from .compact_handoff import compact_handoff
            report = compact_handoff(report)
    elif command == 'status':
        report = dict(state, goal_review_status=goal_review_status(state))
    elif command == 'history':
        report = {'events': state.get('journal', [])}
    elif command == 'coverage':
        validate_approval_workspace(state)
        report = coverage_report(contract, state)
    elif command == 'recovery':
        report = recovery_report(contract, state, find_step(contract, args.step))
    else:
        if not args.contract:
            raise ValueError('revision-diff requires proposed --contract')
        proposed = json.loads(Path(args.contract).read_text(encoding='utf-8-sig'))
        validate(proposed)
        validate_known_fields(proposed)
        report = revision_diff(contract, proposed)
    print(json.dumps(report, indent=2))
    return 0


def run_transition(contract, state, args, root, path):
    """Apply one mutating command and return its exit code once committed."""
    from .approvals import exhaustion_reason, validate_approval_workspace
    from .budgets import step_budget_exhausted
    from .coverage import record_criterion_review
    from .journal import commit_state
    from .publication import now
    from .recovery import reconcile_recovery
    from .revisions import publish_revision
    from . import lifecycle_stop, transitions
    command = args.command
    if command == 'revise':
        publish_revision(root, contract, state, args)
        return 0
    code = None
    if command == 'init':
        transitions.init_mission(contract, state, args, root)
    elif command == 'criterion-review':
        validate_approval_workspace(state)
        record_criterion_review(contract, state, args)
    elif command == 'recover':
        reconcile_recovery(contract, state, transitions.find_step(contract, args.step), args)
    elif command == 'finish':
        code = lifecycle_stop.finish_mission(contract, state)
    elif command == 'goal-review':
        lifecycle_stop.record_goal_review(contract, state, args)
    elif command == 'stop':
        lifecycle_stop.stop_mission(state, args)
    elif command == 'resume':
        lifecycle_stop.resume_mission(contract, state, args)
    else:
        code = transitions.step_transition(contract, state, args, path)
    if code is not None:
        return code
    if (command == 'verify' and not state.get('stop_reason')
            and any(entry.get('budget_exhausted') or entry.get('approval_denied') for entry in state['steps'].values())
            and step_budget_exhausted(contract, state)):
        state['stop_reason'] = exhaustion_reason(state)
    state['last_update'] = now()
    commit_state(path, state, contract, args)
    if command == 'finish':
        lifecycle_stop.print_goal_review_notice(state)
    if command == 'verify':
        return int(state['steps'][args.step]['status'] != 'completed')
    if command == 'goal-review':
        return int(args.verdict == 'fail')
    if command == 'deny':
        return 1
    if command == 'criterion-review':
        return int(args.verdict == 'unmet')
    if command == 'recover':
        return int(args.resolution in ('partial', 'unknown'))
    return 0


def run_mission_command(args, root):
    from .contract import validate_known_fields
    from .publication import digest
    from .storage import persistent_lock, require_regular_lock_entry
    from .store import read_bounded
    from .validation import validate, validate_state
    command = args.command
    if command == 'init':
        root.mkdir(parents=True, exist_ok=True)
    elif not root.is_dir():
        raise ValueError('mission directory does not exist: ' + str(root))
    # Checkpoints are replaced atomically, so reports need no lock and stay usable during verify.
    if command in READ_ONLY_COMMANDS:
        require_regular_lock_entry(root / '.lock')
    guard = contextlib.nullcontext() if command in READ_ONLY_COMMANDS else persistent_lock(root / '.lock')
    with guard:
        if command == 'init' and args.contract:
            contract = json.loads(Path(args.contract).read_text(encoding='utf-8-sig'))
        else:
            contract = json.loads(read_bounded(root / 'contract.json', MAX_STATE_BYTES)[0].decode('utf-8-sig'))
        validate(contract)
        if command == 'init' and args.contract:
            validate_known_fields(contract)
        path = root / 'state/progress.json'
        if command == 'init' and os.path.lexists(path):
            raise ValueError('already initialized or checkpoint entry requires recovery')
        if command != 'init' and not path.exists():
            raise ValueError('initialize mission first')
        if path.exists():
            state = json.loads(read_bounded(path, MAX_STATE_BYTES)[0].decode('utf-8-sig'))
        else:
            state = {'steps': {}, 'attempts': 0, 'stop_reason': None}
        validate_state(state, contract)
        if command != 'init' and state.get('contract_hash') != digest(contract):
            raise ValueError('contract changed; create a new mission revision')
        if command in STEP_COMMANDS and not args.step:
            raise ValueError('--step required')
        if command in READ_ONLY_COMMANDS:
            return run_report(contract, state, args, root)
        return run_transition(contract, state, args, root, path)


def main(argv):
    if argv == ['--version'] or (len(argv) == 2 and argv[0] in ('checks', 'repeat') and argv[1] == '--version'):
        print('Mission Control ' + VERSION)
        return 0
    from .checks import verify
    from .cli_aux import run_helper, run_repeat
    from .cli_parser import build_parser, reject_misplaced_flags
    timeout = float(os.environ.get('VERIFY_TIMEOUT', '60'))
    if not 0 < timeout < float('inf'):
        raise ValueError('VERIFY_TIMEOUT must be finite and positive')
    if argv and argv[0] == 'checks':
        if len(argv) > 1 and argv[1] == '--single':
            return verify(argv[2:])
        return verify(argv[1:], split=True)
    if argv and argv[0] == 'repeat':
        return run_repeat(argv[1:])
    args = build_parser().parse_args(argv)
    reject_misplaced_flags(args)
    root = Path(args.mission)
    code = run_helper(args, root)
    return code if code is not None else run_mission_command(args, root)
