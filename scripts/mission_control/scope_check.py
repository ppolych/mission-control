"""Observe changes outside declared writes; git shows that a path changed, never who changed it."""
from pathlib import Path

from .git_read import GitError, null_separated, repository_prefix, run_git, text
from .settings import MAX_SCOPE_PATHS

STATUSES = ('open', 'stated_mine', 'stated_not_mine')
DISPOSITIONS = {'mine': 'stated_mine', 'not_mine': 'stated_not_mine', 'unknown': 'open'}
OWNERSHIP = 'unverified'


def covered(name, declared):
    return any(name == path or name.startswith(path.rstrip('/') + '/') for path in declared)


def path_digest(workspace, name):
    from .observations import observe_artifact
    from .publication import digest
    try:
        return digest(observe_artifact(workspace, name.rstrip('/')))
    except ValueError:
        return digest({'status': 'unavailable', 'reason': 'unsupported_path'})


def mission_relative(root, workspace):
    if root is None:
        return None
    try:
        return str(Path(root).resolve().relative_to(Path(workspace).resolve()))
    except ValueError:
        return None


def excluded(name, mission):
    return bool(mission) and (name.rstrip('/') == mission or name.startswith(mission + '/'))


def snapshot(workspace, root):
    """Dirty paths and HEAD now; any failure is reported as unavailable, never as clean."""
    try:
        prefix = repository_prefix(workspace)
        head = text(run_git(workspace, 'rev-parse', '--verify', '-q', 'HEAD', ok=(0, 1))) or None
        items = null_separated(run_git(workspace, 'status', '--porcelain=v1', '-z', '--untracked-files=all',
                                       '--no-renames', '--ignore-submodules=dirty', '--', '.'))
    except GitError as error:
        return {'status': 'unavailable', 'reason': str(error)}
    if len(items) > MAX_SCOPE_PATHS:
        return {'status': 'unavailable', 'reason': 'more than ' + str(MAX_SCOPE_PATHS) + ' changed paths'}
    mission = mission_relative(root, workspace)
    paths = {}
    for item in items:
        name = item[3:]
        name = name[len(prefix):] if name.startswith(prefix) else name
        if not excluded(name, mission):
            paths[name] = path_digest(workspace, name)
    return {'status': 'available', 'head': head, 'prefix': prefix, 'paths': paths}


def committed_paths(workspace, before, after, prefix):
    names = null_separated(run_git(workspace, 'diff', '--name-only', '-z', '--no-renames', before, after, '--', '.'))
    return [name[len(prefix):] if name.startswith(prefix) else name for name in names]


def compare(start, end, declared, workspace, root):
    """Return the scope result; every observed path keeps ownership unverified."""
    for value in (start, end):
        if not value or value.get('status') != 'available':
            reason = value.get('reason') if value else 'no snapshot at start'
            return {'status': 'unavailable', 'reason': reason, 'observed': []}
    moved = start['head'] != end['head']
    extra = []
    if moved:
        if not start['head'] or not end['head']:
            return {'status': 'unavailable', 'reason': 'HEAD appeared or vanished during the step', 'observed': []}
        try:
            extra = committed_paths(workspace, start['head'], end['head'], start['prefix'])
        except GitError as error:
            return {'status': 'unavailable', 'reason': str(error), 'observed': []}
    mission = mission_relative(root, workspace)
    observed = []
    for name in sorted(set(start['paths']) | set(end['paths']) | set(extra)):
        if covered(name, declared) or excluded(name, mission):
            continue
        in_commit = name in extra
        if start['paths'].get(name) == end['paths'].get(name) and not in_commit:
            continue
        doubts = (['already_dirty_before_step'] if name in start['paths'] else []) + (['head_moved_during_step'] if moved else [])
        observed.append({'path': name, 'digest': end['paths'].get(name) or path_digest(workspace, name),
                         'ownership': OWNERSHIP, 'doubts': doubts})
    return {'status': 'performed', 'head_moved': moved, 'observed': observed}


def merge_observations(state, step_id, observed):
    records = state.setdefault('scope_observations', {}) if observed else state.get('scope_observations', {})
    for item in observed:
        record = records.get(item['path'], {'notes': []})
        if record.get('digest') != item['digest']:
            record.update(status='open', digest=item['digest'])
        record.update(step=step_id, ownership=OWNERSHIP, doubts=item['doubts'])
        records[item['path']] = record


def begin_step(entry, state, root):
    entry['scope_start'] = snapshot(state['workspace'], root)


def check_step(contract, state, step, entry, root):
    """Record what was seen before checks run; only a declared dedicated workspace can refuse."""
    declared = step['effects']['writes']
    result = compare(entry.get('scope_start'), snapshot(state['workspace'], root), declared, state['workspace'], root)
    names = [item['path'] for item in result['observed']]
    if names and contract.get('workspace_isolation') == 'dedicated':
        raise ValueError('undeclared changes observed in a workspace declared dedicated: ' + ', '.join(names)
                         + '. Nothing was reverted; inspect them, then correct them or publish a contract revision.')
    merge_observations(state, step['id'], result['observed'])
    entry['scope_check'] = result


def current_status(record, name, workspace):
    """A statement only applies to the content it described."""
    return record['status'] if path_digest(workspace, name) == record['digest'] else 'open'


def scope_report(contract, state):
    workspace = state.get('workspace')
    records = state.get('scope_observations', {})
    observations = {name: dict(record, current_status=current_status(record, name, workspace)) for name, record in records.items()}
    checks = {step['id']: state['steps'].get(step['id'], {}).get('scope_check', {'status': 'not_performed', 'reason': 'step not verified'})
              for step in contract['steps']}
    return {'observations': observations, 'steps': checks,
            'open': sorted(name for name, record in observations.items() if record['current_status'] == 'open'),
            'notice': 'Records observed changes and recorded statements. It is not a sandbox and does not prove who made a change.'}


def record_note(contract, state, args):
    from .discipline import is_strict, nonblank
    from .publication import now
    if not is_strict(contract):
        raise ValueError('scope-note requires discipline: strict')
    record = state.get('scope_observations', {}).get(args.path)
    if record is None:
        raise ValueError('scope-note applies only to an observed path; see the scope report')
    if args.disposition not in DISPOSITIONS or not nonblank(args.rationale):
        raise ValueError('scope-note requires --disposition mine|not_mine|unknown and a nonblank --rationale')
    current = path_digest(state['workspace'], args.path)
    record['notes'].append({'disposition': args.disposition, 'rationale': args.rationale, 'digest': current,
                            'timestamp': now(), 'kind': 'recorded statement, not proof'})
    record.update(status=DISPOSITIONS[args.disposition], digest=current)


def validate_scope_state(state):
    records = state.get('scope_observations', {})
    if not isinstance(records, dict):
        raise ValueError('invalid scope observations')
    for record in records.values():
        if (not isinstance(record, dict) or record.get('status') not in STATUSES
                or not isinstance(record.get('digest'), str) or not isinstance(record.get('notes'), list)):
            raise ValueError('invalid scope observation')
    for entry in state['steps'].values():
        for key in ('scope_start', 'scope_check'):
            if key in entry and not isinstance(entry[key], dict):
                raise ValueError('invalid checkpoint scope record')
