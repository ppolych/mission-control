"""Finishing, reviewing, stopping and resuming a mission, and blocking a step."""
from pathlib import Path


def finish_mission(contract, state):
    from .approvals import validate_approval_workspace
    from .coverage import coverage_report, revalidation_hint, stale_steps
    if state.get('stop_reason') not in (None, 'done_verified'):
        raise ValueError('resume before finish')
    if any(state['steps'].get(step['id'], {}).get('status') != 'completed' for step in contract['steps']):
        raise ValueError('incomplete steps')
    if contract['schema_version'] == 3:
        validate_approval_workspace(state)
        if not coverage_report(contract, state)['all_supported']:
            detail = '; ' + revalidation_hint(contract, state) if stale_steps(contract, state) else ''
            raise ValueError('acceptance coverage is unmet, unverified or stale' + detail)
    if state.get('stop_reason') == 'done_verified':
        print_goal_review_notice(state)
        return 0
    state['stop_reason'] = 'done_verified'
    return None


def print_goal_review_notice(state):
    from .reports import goal_review_status
    if goal_review_status(state) == 'missing':
        print('done_verified: steps verified. Required next: inspect the combined outcome against '
              'the original goal and record goal-review --verdict pass|fail --rationale TEXT.')


def record_goal_review(contract, state, args):
    from .approvals import validate_approval_workspace
    from .coverage import coverage_report, revalidation_hint, stale_steps
    from .publication import now
    incomplete = any(state['steps'].get(step['id'], {}).get('status') != 'completed' for step in contract['steps'])
    if state.get('stop_reason') != 'done_verified' or incomplete:
        raise ValueError('goal-review requires successful finish')
    if not args.verdict or not args.rationale or not args.rationale.strip():
        raise ValueError('goal-review requires --verdict and nonblank --rationale')
    if contract['schema_version'] == 3 and args.verdict == 'pass':
        validate_approval_workspace(state)
        if not coverage_report(contract, state)['all_supported']:
            raise ValueError('acceptance evidence changed; cannot record a passing goal review')
    if 'goal_review' in state:
        state.setdefault('goal_review_history', []).append(state['goal_review'])
    state['goal_review'] = {'verdict': args.verdict, 'rationale': args.rationale, 'timestamp': now(),
                            'goal': contract['mission'], 'contract_hash': state['contract_hash']}
    if args.verdict == 'fail':
        state['stop_reason'] = 'blocked'


def stop_mission(state, args):
    from .lifecycle_rules import OPERATOR_STOP_REASONS
    if state.get('stop_reason'):
        raise ValueError('resume before changing stop reason')
    if args.reason not in OPERATOR_STOP_REASONS:
        raise ValueError('invalid stop reason')
    state['stop_reason'] = args.reason


def resume_mission(contract, state, args):
    from .publication import now
    stopped = state.get('stop_reason')
    rationale = args.rationale.strip() if args.rationale else None
    if stopped == 'human_abort' and not rationale:
        raise ValueError('human_abort requires resume --rationale recording the explicit user decision to continue')
    if 'workspace' not in state:
        if not args.workspace:
            raise ValueError('legacy checkpoint: resume --workspace PATH to pin workspace')
        workspace = Path(args.workspace).resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError('workspace must be directory')
        state['workspace'] = str(workspace)
    elif args.workspace:
        raise ValueError('workspace already pinned')
    if 'goal_review' in state:
        state.setdefault('goal_review_history', []).append(state.pop('goal_review'))
    if rationale or stopped in ('human_abort', 'human_paused'):
        state.setdefault('resume_history', []).append({'stopped_by': stopped, 'rationale': rationale, 'timestamp': now()})
    state['stop_reason'] = None
    definitions = {step['id']: step for step in contract['steps']}
    for identifier, entry in state['steps'].items():
        if entry.get('approval_denied'):
            continue
        if (contract['schema_version'] == 3 and entry.get('status') == 'in_progress'
                and not entry.get('revalidating') and definitions[identifier].get('retry', 'inspect') == 'inspect'):
            entry['recovery_required'] = True
        entry.setdefault('history', []).append({'evidence': entry.get('evidence', []),
                                                'manual': entry.get('manual', {}), 'timestamp': now()})
        entry['needs_revalidation'] = entry.get('status') in ('completed', 'in_progress') or entry.get('needs_revalidation', False)
        entry['status'] = 'pending'
        entry['evidence'] = []
        entry['manual'] = {}
        entry.pop('approval_request', None)
    state['resume_note'] = 'Revalidate completed work; inspect interrupted actions before retrying.'


def block_step(contract, step, entry, args):
    if entry.get('status') != 'in_progress':
        raise ValueError('block requires the active step; use resume to reopen completed work')
    if not args.reason or not args.reason.strip():
        raise ValueError('block requires a nonempty --reason')
    entry['status'] = 'blocked'
    entry['diagnosis'] = args.reason
    if contract['schema_version'] == 3 and step.get('retry', 'inspect') == 'inspect' and not entry.get('revalidating'):
        entry['recovery_required'] = True
