"""Reserving a step attempt, including every start refusal."""


def start_step(contract, state, step, entry, args, path):
    from .approvals import exhaustion_reason, has_approval, request_approval, requires_approval, validate_approval_workspace
    from .budgets import attempts_per_step, mission_attempts, step_budget_exhausted
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
        # A repeated refusal changes nothing, so it must not grow the journal.
        if step_budget_exhausted(contract, state):
            state['stop_reason'] = 'blocked'
            state['last_update'] = now()
            commit_state(path, state, contract, args)
        return 1
    if args.revalidate and not entry.get('needs_revalidation'):
        raise ValueError('no interrupted or completed work to revalidate')
    if entry.get('needs_revalidation') and not args.revalidate:
        raise ValueError('inspect prior work and start --revalidate first')
    if entry.get('status') == 'completed':
        raise ValueError('step already completed')
    if active:
        raise ValueError('another step active')
    if dependency_open:
        raise ValueError('dependency incomplete')
    if not args.revalidate and state['attempts'] >= mission_attempts(contract):
        state['stop_reason'] = 'max_iterations'
        state['last_update'] = now()
        commit_state(path, state, contract, args)
        return 1
    if not args.revalidate and entry.get('attempts', 0) >= attempts_per_step(contract):
        changed = not entry.get('budget_exhausted')
        entry['budget_exhausted'] = True
        if step_budget_exhausted(contract, state):
            state['stop_reason'] = exhaustion_reason(state)
            changed = True
        if changed:
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
    if entry.get('manual') or entry.get('evidence'):
        entry.setdefault('history', []).append({'manual': entry.get('manual', {}), 'evidence': entry.get('evidence', []), 'timestamp': now()})
    entry['evidence'] = []
    entry.pop('failed_verification', None)
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
