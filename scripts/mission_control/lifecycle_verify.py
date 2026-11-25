"""Recording manual assessments and running step verification."""
from pathlib import Path


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


def verify_step(contract, state, step, entry, args=None, path=None):
    from .approvals import has_approval, requires_approval, validate_approval_workspace
    from .checks import run_check
    from .budgets import no_progress_threshold
    from .coverage import verification_artifacts
    from .discipline import step_outcome
    from .observations import readable_observations
    from .publication import digest, now
    from .settings import MAX_JOURNAL_EVENTS
    schema3 = contract['schema_version'] == 3
    if entry.get('status') != 'in_progress':
        if entry.get('recovery_required'):
            from .lifecycle_start import recovery_needed
            raise ValueError(recovery_needed(step))
        raise ValueError('start step first: start --step ' + step['id'])
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
    outcome = step_outcome(contract, state, step, entry, args, Path(path).parent.parent if path else None)
    results = []
    counted = counted_test_check(contract, state, step)
    for index, check in sorted(enumerate(step['verify']), key=lambda pair: isinstance(pair[1], dict)):
        if isinstance(check, list):
            result = run_check(check, quiet=True, cwd=workspace, timeout=step.get('verify_timeout'), index=index,
                               grade=schema3, require_tests=check == counted)
        else:
            result = {'code': int(manual.get(str(index), {}).get('verdict') != 'pass'),
                      'command_exit_status': None, 'signal': None, 'error_type': None}
        results.append(dict(result, check=index, identity=check, timestamp=now(), cwd=str(workspace), output_policy='discarded'))
        if result['code']:
            break
    failed = any(result['code'] for result in results)
    if failed:
        print_similar_paths(results, state)
    if schema3 and not failed:
        validate_approval_workspace(state)
        if requires_approval(contract, step) and not has_approval(contract, step, state):
            raise ValueError('approval inputs changed during verification; inspect and obtain current approval before revalidation')
        receipt = verification_artifacts(step, state['workspace'])
        readable_observations(receipt)
    entry.setdefault('history', []).append({'evidence': entry.get('evidence', []), 'timestamp': now()})
    entry['evidence'] = results
    entry['status'] = 'pending' if failed else 'completed'
    entry['failed_verification'] = failed
    if schema3:
        if failed:
            entry.pop('verified_artifacts', None)
        else:
            entry['verified_artifacts'] = receipt
            if outcome:
                if 'test_first' in step:
                    outcome['tests'] = test_count(step, results)
                entry['discipline_outcome'] = outcome
                entry.pop('scope_start', None)
    entry['needs_revalidation'] = False
    if failed and schema3 and step.get('retry', 'inspect') == 'inspect' and not entry.get('revalidating'):
        entry['recovery_required'] = True
    key = digest([step['verify'], entry.get('context'), [result['check'] for result in results if result['code']]])
    failures = entry.setdefault('failures', {})
    if not failed:
        failures.clear()
    else:
        failures[key] = failures.get(key, 0) + 1
    if failed and failures[key] >= no_progress_threshold(contract):
        state['stop_reason'] = 'no_progress'


def counted_test_check(contract, state, step):
    """The check whose tests must be counted: the test_first command, for missions started by 0.4.2.13 or later."""
    from .discipline import is_strict
    value = step.get('test_first')
    if 'controller' not in state or not is_strict(contract) or not value or 'uncounted_reason' in value:
        return None
    return ['exit0', *value['command']]


def test_count(step, results):
    """What the final report can say about the tests behind red/green."""
    if 'uncounted_reason' in step['test_first']:
        return {'tier': 'uncounted', 'reason': step['test_first']['uncounted_reason']}
    command = ['exit0', *step['test_first']['command']]
    for result in results:
        if result.get('identity') == command and 'grade' in result:
            return result['grade']
    return {'tier': 'unknown'}


def print_similar_paths(results, state):
    """A declared file that is missing while a similar undeclared one appeared is usually a naming slip."""
    observed = sorted(state.get('scope_observations', {}))
    for result in results:
        check = result['identity']
        if not result['code'] or not isinstance(check, list) or check[0] != 'file':
            continue
        stem = Path(check[1]).name.split('.')[0].lower()
        similar = [name for name in observed if stem and stem in Path(name).name.lower() and name != check[1]]
        if similar:
            print('hint: ' + check[1] + ' is declared but missing, and ' + ', '.join(similar[:3]) + ' appeared without being '
                  'declared; write the declared path, or change the contract with revise (references/mission-guide.md)')
