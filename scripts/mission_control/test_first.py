"""Red/green evidence for a step that declares test_first: recorded facts, not proof of a good test."""
import os

from .settings import MAX_OBSERVED_BYTES

NOT_RUNNABLE_STATUSES = (126, 127)


def implementation_paths(step):
    tests = set(step['test_first']['test_paths'])
    return [name for name in step['effects']['writes'] if name not in tests]


def validate_test_first(step):
    if 'test_first' not in step:
        return
    import re
    from .validation import check_args
    label = step['id'] + ': test_first '
    value = step['test_first']
    if 'test_first_exempt' in step:
        raise ValueError(label + 'and test_first_exempt cannot both be declared')
    if not isinstance(value, dict) or not {'command', 'test_paths'} <= set(value) or set(value) - {'command', 'test_paths', 'failure_matches'}:
        raise ValueError(label + 'needs command and test_paths, with optional failure_matches')
    command = value['command']
    try:
        check_args(['exit0', *command] if isinstance(command, list) else None)
    except (ValueError, TypeError) as error:
        raise ValueError(label + 'command must be a nonempty argv array') from error
    if ['exit0', *command] not in step['verify']:
        raise ValueError(label + 'command must also be declared as an exit0 check of the step')
    paths = value['test_paths']
    writes = step['effects']['writes']
    if not isinstance(paths, list) or not paths or set(map(str, paths)) - set(writes):
        raise ValueError(label + 'test_paths must be a nonempty subset of effects.writes; list an existing test too, which does not require changing it')
    if not implementation_paths(step):
        raise ValueError(label + 'needs at least one declared write that is not a test')
    if 'failure_matches' in value:
        try:
            re.compile(value['failure_matches'])
        except (re.error, TypeError) as error:
            raise ValueError(label + 'failure_matches is not a valid pattern') from error


def run_captured(command, workspace, timeout):
    """Return (status, output); output stays in a temporary file and is never stored."""
    import tempfile
    from .processes import supervised_process
    with tempfile.TemporaryFile() as stream:
        process = supervised_process(command, workspace, False, timeout, output=stream)
        stream.seek(0)
        return process.returncode, stream.read(MAX_OBSERVED_BYTES).decode('utf-8', 'replace')


def refuse(message):
    import sys
    print('red not recorded: ' + message, file=sys.stderr)
    return 1


def record_red(contract, state, step, entry):
    """Return 1 when the command is not red; None when a new red record must be committed."""
    import re
    import subprocess
    from .approvals import has_approval, requires_approval, validate_approval_workspace
    from .discipline import is_strict
    from .observations import artifact_observations, observations, readable_observations
    from .publication import now
    if not is_strict(contract) or 'test_first' not in step:
        raise ValueError('red requires discipline: strict and a step declaring test_first')
    if entry.get('status') != 'in_progress' or entry.get('revalidating'):
        raise ValueError('red requires the active step, not checks-only revalidation')
    if requires_approval(contract, step) and not has_approval(contract, step, state):
        raise ValueError('step approval missing or stale; resume and request approval again')
    validate_approval_workspace(state)
    workspace = state['workspace']
    declared = step['test_first']
    baseline = entry.get('first_effect_baseline', {})
    implementation = artifact_observations(workspace, implementation_paths(step))
    started = sorted(name for name, value in implementation.items() if baseline.get(name) != value)
    if started and 'red' not in entry:
        raise ValueError('implementation already changed (' + ', '.join(started) + '), so a failure now would not show the '
                         'earlier state; record test-first-note --reason TEXT instead of undoing work')
    if started and implementation != entry['red']['implementation']:
        raise ValueError('implementation changed since the last red; record test-first-note --reason TEXT instead of undoing work')
    digests = observations(workspace, declared['test_paths'])
    readable_observations(digests)
    limit = step.get('verify_timeout', float(os.environ.get('VERIFY_TIMEOUT', '60')))
    try:
        status, output = run_captured(declared['command'], workspace, limit)
    except subprocess.TimeoutExpired:
        return refuse('command timed out')
    except OSError as error:
        return refuse('command could not run: ' + type(error).__name__)
    if status == 0:
        return refuse('command passed; a failing test must come first')
    if status < 0 or status in NOT_RUNNABLE_STATUSES:
        return refuse('command could not run to a test result (status ' + str(status) + ')')
    pattern = declared.get('failure_matches')
    if pattern is not None and not re.search(pattern, output):
        return refuse('failure output did not match failure_matches; this looks like a different failure. Fix the test, record test-first-note '
                      '--reason TEXT, or use revise for a new pattern. Do not delete the mission directory to start over.')
    if 'red' in entry:
        entry.setdefault('red_history', []).append(entry['red'])
    entry['red'] = {'exit_status': status, 'failure_match': 'matched' if pattern is not None else 'exit_only',
                    'test_digests': digests, 'implementation': implementation, 'timestamp': now()}
    return None


def record_note(contract, step, entry, args):
    from .discipline import is_strict, nonblank
    from .publication import now
    if not is_strict(contract) or 'test_first' not in step:
        raise ValueError('test-first-note requires discipline: strict and a step declaring test_first')
    if entry.get('status') != 'in_progress':
        raise ValueError('test-first-note requires the active step')
    if not nonblank(args.reason):
        raise ValueError('test-first-note requires a nonblank --reason')
    entry.setdefault('test_first_notes', []).append({'reason': args.reason, 'timestamp': now()})


def red_green_status(step, entry, workspace):
    """Confirmed needs red, the same test files and a changed implementation; a note makes it unconfirmed."""
    from .observations import artifact_observations, observations
    red = entry.get('red')
    problem = 'no red was recorded'
    if red:
        if observations(workspace, step['test_first']['test_paths']) != red['test_digests']:
            problem = 'test files changed after red'
        elif artifact_observations(workspace, implementation_paths(step)) == red['implementation']:
            problem = 'implementation did not change since red'
        else:
            return {'red_green': 'confirmed', 'failure_match': red['failure_match']}
    notes = entry.get('test_first_notes')
    if notes:
        return {'red_green': 'unconfirmed', 'test_first_notes': notes}
    raise ValueError(problem + '; run red before implementing, or record test-first-note --reason TEXT, '
                     'which marks the result unconfirmed. Do not undo work to satisfy this.')


def needs_red(contract, step, entry):
    from .discipline import is_strict
    return (is_strict(contract) and 'test_first' in step and not entry.get('revalidating')
            and 'red' not in entry and not entry.get('test_first_notes'))
