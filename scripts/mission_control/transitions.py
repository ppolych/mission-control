"""Mission initialization and dispatch of step commands."""
from pathlib import Path


def find_step(contract, identifier):
    for step in contract['steps']:
        if step['id'] == identifier:
            return step
    known = ', '.join(step['id'] for step in contract['steps'])
    raise ValueError('unknown step: ' + str(identifier) + '; contract steps: ' + known)


def require_mission_outside_outputs(contract, workspace, root):
    """Checkpoint writes would otherwise change a declared artifact forever."""
    if contract['schema_version'] != 3:
        return
    mission = root.resolve()
    for step in contract['steps']:
        for name in step['effects']['writes'] + step.get('watch', []):
            target = (workspace / name).resolve()
            if mission == target or mission.is_relative_to(target):
                raise ValueError('mission directory ' + str(mission) + ' is inside declared path ' + name
                                 + '; choose a mission directory outside declared outputs and watched inputs')


def init_mission(contract, state, args, root):
    from .contract import validate_allowed_paths
    from .publication import digest
    from .settings import MAX_STATE_BYTES
    from .storage import atomic
    from .store import read_bounded
    import json
    import os
    workspace = Path(args.workspace or Path.cwd()).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError('workspace must be directory')
    validate_allowed_paths(contract, workspace)
    require_mission_outside_outputs(contract, workspace, root)
    destination = root / 'contract.json'
    if os.path.lexists(destination):
        if destination.is_symlink():
            raise ValueError('destination contract must not be a symlink')
        existing = json.loads(read_bounded(destination, MAX_STATE_BYTES)[0].decode('utf-8-sig'))
        if existing != contract:
            raise ValueError('destination contract differs; use a new mission directory')
    else:
        atomic(destination, contract)
    state['contract_hash'] = digest(contract)
    state['workspace'] = str(workspace)
    state['approved_steps'] = {}


def step_transition(contract, state, args, path):
    from .approvals import record_decision
    from .budgets import step_budget_exhausted
    from .lifecycle_start import start_step
    from .lifecycle_stop import block_step
    from .lifecycle_verify import assess_step, verify_step
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
    elif args.command == 'red':
        from .test_first import record_red
        return record_red(contract, state, step, entry)
    elif args.command == 'test-first-note':
        from .test_first import record_note
        record_note(contract, step, entry, args)
    else:
        verify_step(contract, state, step, entry, args, path)
    return None
