"""Checkpoint transitions; handlers return an exit code only to skip the shared commit."""
from pathlib import Path


def find_step(contract, identifier):
    for step in contract['steps']:
        if step['id'] == identifier:
            return step
    known = ', '.join(step['id'] for step in contract['steps'])
    raise ValueError('unknown step: ' + str(identifier) + '; contract steps: ' + known)


def init_mission(contract, state, args, root):
    from .contract import validate_allowed_paths
    from .publication import digest
    from .storage import atomic
    import json
    import os
    workspace = Path(args.workspace or Path.cwd()).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError('workspace must be directory')
    validate_allowed_paths(contract, workspace)
    destination = root / 'contract.json'
    if os.path.lexists(destination):
        if destination.is_symlink():
            raise ValueError('destination contract must not be a symlink')
        existing = json.loads(destination.read_text(encoding='utf-8-sig'))
        if existing != contract:
            raise ValueError('destination contract differs; use a new mission directory')
    else:
        atomic(destination, contract)
    state['contract_hash'] = digest(contract)
    state['workspace'] = str(workspace)
    state['approved_steps'] = {}


def finish_mission(contract, state):
    from .approvals import validate_approval_workspace
    from .coverage import coverage_report
    if state.get('stop_reason') not in (None, 'done_verified'):
        raise ValueError('resume before finish')
    if any(state['steps'].get(step['id'], {}).get('status') != 'completed' for step in contract['steps']):
        raise ValueError('incomplete steps')
    if contract['schema_version'] == 3:
        validate_approval_workspace(state)
        if not coverage_report(contract, state)['all_supported']:
            raise ValueError('acceptance coverage is unmet, unverified or stale')
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
    from .coverage import coverage_report
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
    if state.get('stop_reason'):
        raise ValueError('resume before changing stop reason')
    if args.reason not in ('blocked', 'human_paused', 'human_abort', 'no_progress', 'budget_exhausted', 'max_iterations'):
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


def start_step(contract, state, step, entry, args, path):
    from .approvals import exhaustion_reason, has_approval, request_approval, requires_approval, validate_approval_workspace
    from .budgets import step_budget_exhausted
    from .journal import commit_state
    from .observations import artifact_observations, readable_observations, watched_inputs
    from .publication import now
    import json
    schema3 = contract['schema_version'] == 3
    if schema3:
        validate_approval_workspace(state)
        if entry.get('recovery_required'):
            raise ValueError('inspect recovery report and reconcile before retry or revalidation')
    active = any(value.get('status') == 'in_progress' for value in state['steps'].values())
    dependency_open = any(state['steps'].get(name, {}).get('status') != 'completed' for name in step.get('depends_on', []))
    if entry.get('approval_denied'):
        if active:
            raise ValueError('another step active')
        if dependency_open:
            raise ValueError('dependency incomplete')
        if step_budget_exhausted(contract, state):
            state['stop_reason'] = 'blocked'
        state['last_update'] = now()
        commit_state(path, state, contract, args)
        return 1
    if args.revalidate and not entry.get('needs_revalidation'):
        raise ValueError('no interrupted or completed work to revalidate')
    if entry.get('needs_revalidation') and not args.revalidate:
        raise ValueError('inspect prior work and start --revalidate first')
    if state.get('stop_reason'):
        raise ValueError('resume mission first')
    if entry.get('status') == 'completed':
        raise ValueError('step already completed')
    if active:
        raise ValueError('another step active')
    if dependency_open:
        raise ValueError('dependency incomplete')
    budget = contract.get('budget', {})
    limit = budget.get('max_iterations', max(10, 3 * len(contract['steps'])))
    if not args.revalidate and state['attempts'] >= limit:
        state['stop_reason'] = 'max_iterations'
        commit_state(path, state, contract, args)
        return 1
    if not args.revalidate and entry.get('attempts', 0) >= budget.get('max_attempts_per_step', 2):
        entry['budget_exhausted'] = True
        if step_budget_exhausted(contract, state):
            state['stop_reason'] = exhaustion_reason(state)
        state['last_update'] = now()
        commit_state(path, state, contract, args)
        return 1
    if schema3 or requires_approval(contract, step):
        validate_approval_workspace(state)
    if requires_approval(contract, step) and not has_approval(contract, step, state):
        request = request_approval(contract, step, state, args.revalidate)
        state['last_update'] = now()
        commit_state(path, state, contract, args)
        print(json.dumps(request, indent=2))
        return 3
    if entry.get('manual'):
        entry.setdefault('history', []).append({'manual': entry['manual'], 'evidence': entry.get('evidence', []), 'timestamp': now()})
    if schema3 and not args.revalidate:
        entry['effect_baseline'] = artifact_observations(state['workspace'], step['effects']['writes'])
        readable_observations(entry['effect_baseline'])
        entry['input_baseline'] = watched_inputs(contract, step, state['workspace'])
        readable_observations(entry['input_baseline'])
    entry['context'] = args.context
    entry['manual'] = {}
    entry['status'] = 'in_progress'
    entry['revalidating'] = args.revalidate
    if args.revalidate:
        entry['revalidations'] = entry.get('revalidations', 0) + 1
    else:
        entry['attempts'] = entry.get('attempts', 0) + 1
        state['attempts'] += 1
    return None


def block_step(contract, step, entry, args):
    if entry.get('status') != 'in_progress':
        raise ValueError('block requires the active step; use resume to reopen completed work')
    if not args.reason or not args.reason.strip():
        raise ValueError('block requires a nonempty --reason')
    entry['status'] = 'blocked'
    entry['diagnosis'] = args.reason
    if contract['schema_version'] == 3 and step.get('retry', 'inspect') == 'inspect' and not entry.get('revalidating'):
        entry['recovery_required'] = True


def assess_step(contract, state, step, entry, args):
    from .approvals import has_approval, requires_approval, validate_approval_workspace
    from .publication import now
    if (entry.get('status') != 'in_progress' or args.check is None or not args.rationale
            or not args.rationale.strip() or not args.verdict):
        raise ValueError('assessment needs active step, check index, verdict and rationale')
    if args.check < 0 or args.check >= len(step['verify']) or not isinstance(step['verify'][args.check], dict):
        raise ValueError('not a manual check')
    if requires_approval(contract, step) and not has_approval(contract, step, state):
        raise ValueError('step approval missing or stale; resume and request approval again')
    if contract['schema_version'] == 3 or requires_approval(contract, step):
        validate_approval_workspace(state)
    entry.setdefault('manual', {})[str(args.check)] = {'verdict': args.verdict, 'rationale': args.rationale, 'timestamp': now()}


def verify_step(contract, state, step, entry):
    from .approvals import has_approval, requires_approval, validate_approval_workspace
    from .checks import run_check
    from .coverage import verification_artifacts
    from .observations import readable_observations
    from .publication import digest, now
    from .settings import MAX_JOURNAL_EVENTS
    schema3 = contract['schema_version'] == 3
    if entry.get('status') != 'in_progress':
        raise ValueError('start step first')
    if requires_approval(contract, step) and not has_approval(contract, step, state):
        raise ValueError('step approval missing or stale; resume and request approval again')
    if schema3 or requires_approval(contract, step):
        validate_approval_workspace(state)
    if 'workspace' not in state:
        raise ValueError('legacy checkpoint: resume --workspace PATH first')
    workspace = Path(state['workspace'])
    if not workspace.is_absolute() or not workspace.is_dir():
        raise ValueError('pinned workspace unavailable')
    manual = entry.get('manual', {})
    missing = [index for index, check in enumerate(step['verify']) if isinstance(check, dict) and str(index) not in manual]
    if missing:
        raise ValueError('missing manual assessments: ' + str(missing) + '; assess then verify the active attempt')
    if any(value.get('verdict') == 'unverified' for value in manual.values()):
        raise ValueError('manual assessment is unverified; assess the active attempt before verification')
    if schema3 and len(state['journal']) >= MAX_JOURNAL_EVENTS:
        raise ValueError('journal event limit reached; refusing checks before an uncommittable verification')
    results = []
    for index, check in sorted(enumerate(step['verify']), key=lambda pair: isinstance(pair[1], dict)):
        if isinstance(check, list):
            result = run_check(check, quiet=True, cwd=workspace, timeout=step.get('verify_timeout'), index=index)
        else:
            result = {'code': int(manual.get(str(index), {}).get('verdict') != 'pass'),
                      'command_exit_status': None, 'signal': None, 'error_type': None}
        results.append(dict(result, check=index, identity=check, timestamp=now(), cwd=str(workspace), output_policy='discarded'))
        if result['code']:
            break
    failed = any(result['code'] for result in results)
    if schema3 and not failed:
        validate_approval_workspace(state)
        if requires_approval(contract, step) and not has_approval(contract, step, state):
            raise ValueError('approval inputs changed during verification; inspect and obtain current approval before revalidation')
        receipt = verification_artifacts(step, state['workspace'])
        readable_observations(receipt)
    entry.setdefault('history', []).append({'evidence': entry.get('evidence', []), 'timestamp': now()})
    entry['evidence'] = results
    entry['status'] = 'pending' if failed else 'completed'
    if schema3:
        if failed:
            entry.pop('verified_artifacts', None)
        else:
            entry['verified_artifacts'] = receipt
    entry['needs_revalidation'] = False
    if failed and schema3 and step.get('retry', 'inspect') == 'inspect' and not entry.get('revalidating'):
        entry['recovery_required'] = True
    key = digest([step['verify'], entry.get('context'), [result['check'] for result in results if result['code']]])
    failures = entry.setdefault('failures', {})
    if not failed:
        failures.clear()
    else:
        failures[key] = failures.get(key, 0) + 1
    if failed and failures[key] >= contract.get('budget', {}).get('no_progress_threshold', 2):
        state['stop_reason'] = 'no_progress'


def step_transition(contract, state, args, path):
    from .approvals import record_decision
    from .budgets import step_budget_exhausted
    from .publication import now
    step = find_step(contract, args.step)
    entry = state['steps'].setdefault(args.step, {})
    if state.get('stop_reason'):
        raise ValueError('resume mission first')
    if args.command == 'start':
        return start_step(contract, state, step, entry, args, path)
    if args.command in ('approve', 'deny'):
        record_decision(contract, step, state, args.command, args.digest, args.rationale, now())
        if args.command == 'deny' and step_budget_exhausted(contract, state):
            state['stop_reason'] = 'blocked'
    elif args.command == 'block':
        block_step(contract, step, entry, args)
    elif args.command == 'assess':
        assess_step(contract, state, step, entry, args)
    else:
        verify_step(contract, state, step, entry)
    return None
