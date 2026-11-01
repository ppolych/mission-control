import hashlib, json, re
from pathlib import Path


def requires_approval(contract, step):
    return contract.get('mode', 'autonomous') == 'controlled' and (
        step.get('needs_approval', False) or step.get('risk', 'low') == 'high')


def validate_policy(contract):
    if contract.get('mode', 'autonomous') not in ('controlled', 'autonomous'):
        raise ValueError('mode must be controlled or autonomous')
    for step in contract.get('steps', []):
        if not isinstance(step, dict):
            continue  # The existing structural validator owns this error.
        if step.get('risk', 'low') not in ('low', 'medium', 'high'):
            raise ValueError('risk must be low, medium or high')
        if type(step.get('needs_approval', False)) is not bool:
            raise ValueError('needs_approval must be a boolean')
        if 'commands' in step:
            commands = step['commands']
            if not isinstance(commands, list):
                raise ValueError('commands must be an array of exact argv arrays')
            for argv in commands:
                if (not isinstance(argv, list) or not argv
                        or not all(isinstance(arg, str) and '\x00' not in arg for arg in argv)
                        or not argv[0].strip()):
                    raise ValueError('invalid command argv')
        if requires_approval(contract, step):
            if 'commands' not in step:
                raise ValueError('controlled gated steps require explicit commands ([] for no commands)')
            if not isinstance(step.get('description'), str) or not step['description'].strip():
                raise ValueError('controlled gated steps require a nonblank description')


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_approval_state(state, contract):
    approved = state.get('approved_steps', {})
    if not isinstance(approved, dict):
        raise ValueError('invalid approved_steps mapping')
    ids = {step['id'] for step in contract['steps']}
    def valid_record(record):
        return (isinstance(record, dict) and valid_digest(record.get('digest'))
                and all(isinstance(record.get(key), str) and record[key].strip()
                        for key in ('timestamp', 'rationale')))
    for identifier, record in approved.items():
        if identifier not in ids or not valid_record(record):
            raise ValueError('invalid step approval record')
    for step in contract['steps']:
        entry = state['steps'].get(step['id'], {})
        if 'approval_denied' in entry and type(entry['approval_denied']) is not bool:
            raise ValueError('invalid approval_denied flag')
        if entry.get('approval_denied'):
            if (entry.get('status') != 'blocked' or step['id'] in approved
                    or not valid_record(entry.get('approval_denial'))):
                raise ValueError('denied steps must stay blocked with a denial record and no approval')
        if entry.get('status') == 'awaiting_approval':
            request = entry.get('approval_request')
            if (not requires_approval(contract, step) or not isinstance(request, dict)
                    or request.get('status') != 'awaiting_approval'
                    or request.get('step') != step
                    or type(request.get('revalidate')) is not bool
                    or not isinstance(request.get('workspace'), str)
                    or not Path(request['workspace']).is_absolute()
                    or (contract['schema_version'] == 3 and step.get('watch') and
                        (not isinstance(request.get('inputs'), dict) or set(request['inputs']) != set(step['watch'])))
                    or request.get('digest') != approval_digest(contract, step, request['workspace'], request.get('inputs'))):
                raise ValueError('invalid pending approval request')


def approval_digest(contract, step, workspace, inputs=None):
    from .observations import watched_inputs
    # Bind the entire frozen contract (including mode, constraints, commands,
    # risks and verify criteria) AND the pinned workspace, not just a step ID.
    payload = {'contract': contract, 'step_id': step['id'], 'workspace': workspace}
    if contract['schema_version'] == 3 and step.get('watch'):
        payload['inputs'] = watched_inputs(contract, step, workspace) if inputs is None else inputs
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def has_approval(contract, step, state):
    record = state.get('approved_steps', {}).get(step['id'], {})
    return record.get('digest') == approval_digest(contract, step, state.get('workspace'))


def validate_approval_workspace(state):
    """A reviewed canonical path must still resolve to that same workspace."""
    value = state.get('workspace')
    if not isinstance(value, str) or not value:
        raise ValueError('pinned workspace unavailable; resume legacy state first')
    workspace = Path(value)
    try:
        if not workspace.is_absolute() or not workspace.is_dir() or workspace.resolve(strict=True) != workspace:
            raise ValueError('pinned workspace unavailable or redirected; inspect before recovery')
    except (OSError, RuntimeError) as error:
        raise ValueError('pinned workspace unavailable or redirected; inspect before recovery') from error


def request_approval(contract, step, state, revalidate):
    from .observations import readable_observations, watched_inputs
    inputs = watched_inputs(contract, step, state['workspace'])
    readable_observations(inputs)
    request = {'status': 'awaiting_approval', 'step': step,
               'workspace': state['workspace'], 'revalidate': revalidate,
               'digest': approval_digest(contract, step, state['workspace'], inputs)}
    if inputs:request['inputs'] = inputs
    entry = state['steps'].setdefault(step['id'], {})
    entry.setdefault('attempts', 0)
    entry['status'] = 'awaiting_approval'
    entry['approval_request'] = request
    state.setdefault('approved_steps', {}).pop(step['id'], None)
    return request


def record_decision(contract, step, state, verdict, supplied_digest, rationale, timestamp):
    entry = state['steps'].get(step['id'], {})
    request = entry.get('approval_request', {})
    expected = approval_digest(contract, step, state.get('workspace'),
                               request.get('inputs') if verdict == 'deny' else None)
    if (not requires_approval(contract, step) or entry.get('status') != 'awaiting_approval'
            or request.get('digest') != expected or supplied_digest != expected
            or request.get('step') != step or request.get('workspace') != state.get('workspace')):
        raise ValueError('decision requires the current presented approval request and --digest')
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError('decision requires explicit user approval/denial and nonblank --rationale')
    if verdict == 'approve':
        validate_approval_workspace(state)
    record = {'digest': expected, 'timestamp': timestamp, 'rationale': rationale}
    if request.get('inputs'):record['inputs'] = request['inputs']
    entry.pop('approval_request', None)
    if verdict == 'approve':
        state.setdefault('approved_steps', {})[step['id']] = record
        entry['status'] = 'pending'
    else:
        state.setdefault('approved_steps', {}).pop(step['id'], None)
        entry.update(status='blocked', approval_denied=True, needs_revalidation=False,
                     diagnosis='user_denied: ' + rationale, approval_denial=record)


def exhaustion_reason(state):
    return 'blocked' if any(e.get('approval_denied') for e in state['steps'].values()) else 'budget_exhausted'

