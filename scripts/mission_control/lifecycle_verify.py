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


def verify_step(contract, state, step, entry, args=None):
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
    outcome = step_outcome(contract, state, step, entry, args)
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
    entry['failed_verification'] = failed
    if schema3:
        if failed:
            entry.pop('verified_artifacts', None)
        else:
            entry['verified_artifacts'] = receipt
            if outcome:
                entry['discipline_outcome'] = outcome
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
