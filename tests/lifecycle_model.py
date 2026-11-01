"""Seeded random command sequences for lifecycle invariant tests."""
import contextlib
import io
import json
import os
from pathlib import Path
import random
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from mission_control.cli import main  # noqa: E402
from mission_control.validation import validate_state  # noqa: E402

REPORTS = (('status',), ('history',), ('handoff',), ('handoff', '--compact'), ('metrics',), ('diagnose',))
STOP_REASONS = ('blocked', 'human_paused', 'human_abort', 'no_progress', 'budget_exhausted', 'max_iterations')
RESOLUTIONS = ('completed', 'not_applied', 'applied_incorrect', 'partial', 'unknown')
HANDLED = (ValueError, OSError, KeyError, StopIteration, TypeError, IndexError)


def build_contract(rng):
    schema = rng.choice((2, 3))
    mode = rng.choice(('autonomous', 'controlled'))
    steps = [{'id': 's1', 'description': 'first', 'verify': [['file', 'ok.txt']], 'needs_approval': mode == 'controlled',
              'commands': []},
             {'id': 's2', 'description': 'second', 'depends_on': ['s1'],
              'verify': [['exit0', 'true'], {'manual': 'inspect the result'}]},
             {'id': 's3', 'description': 'independent', 'verify': [['grep', 'good', 'ok.txt']]}]
    contract = {'schema_version': schema, 'mission': 'random lifecycle', 'mode': mode, 'steps': steps,
                'budget': {'max_attempts_per_step': rng.choice((1, 2, 3)), 'no_progress_threshold': rng.choice((1, 2, 3)),
                           'max_iterations': rng.choice((3, 6, 12))}}
    if schema == 3:
        contract['acceptance'] = [{'id': 'A' + step['id'], 'description': step['description']} for step in steps]
        for step in steps:
            step.update(acceptance_refs=['A' + step['id']], retry=rng.choice(('safe', 'inspect')),
                        effects={'reads': [], 'writes': ['ok.txt'], 'network': 'none',
                                 'external_actions': [], 'reversible': True})
    return contract


def build_operations(rng, count):
    def step():
        return rng.choice(('s1', 's2', 's3'))
    def choose():
        kind = rng.choice(('start', 'start', 'start', 'revalidate', 'verify', 'verify', 'verify', 'assess', 'block', 'stop',
                           'resume', 'approve', 'deny', 'recover', 'review', 'finish', 'goal', 'good', 'bad', 'remove', 'report'))
        if kind == 'stop':
            return (kind, rng.choice(STOP_REASONS))
        if kind == 'recover':
            return (kind, step(), rng.choice(RESOLUTIONS))
        if kind == 'review':
            return (kind, step(), rng.choice(('supported', 'unmet', 'unverified')))
        if kind == 'goal':
            return (kind, rng.choice(('pass', 'fail')))
        if kind == 'assess':
            return (kind, rng.choice(('pass', 'fail', 'unverified')))
        if kind == 'report':
            return (kind, rng.randrange(len(REPORTS)))
        if kind in ('start', 'revalidate', 'verify', 'block', 'approve', 'deny'):
            return (kind, step())
        return (kind,)
    return [choose() for _ in range(count)]


class Mission:
    """Runs one operation list in a disposable mission and checks invariants after each."""

    def __init__(self, contract, root):
        self.contract = contract
        self.root = Path(root)
        self.mission = self.root / '.mission'
        self.path = self.mission / 'state/progress.json'
        (self.root / 'contract.json').write_text(json.dumps(contract))
        code = self.cli('init', '--contract', str(self.root / 'contract.json'), '--workspace', str(self.root))
        assert code == 0, 'init failed'
        self.previous = self.load()

    def cli(self, command, *args):
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                return main([command, '--mission', str(self.mission), *args])
        except HANDLED:
            return 2
        except SystemExit as error:
            return error.code

    def load(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def digest_for(self, step):
        request = self.load()['steps'].get(step, {}).get('approval_request')
        return request['digest'] if request else '0' * 64

    def recovery_digest(self, step):
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                main(['recovery', '--mission', str(self.mission), '--step', step])
            return json.loads(output.getvalue())['digest']
        except HANDLED + (json.JSONDecodeError,):
            return '0' * 64

    def perform(self, operation):
        """Return the exit code and whether the operation must not change the checkpoint."""
        kind, *values = operation
        target = self.root / 'ok.txt'
        if kind in ('good', 'bad'):
            target.write_text(kind + '\n')
            return 0, False
        if kind == 'remove':
            target.unlink(missing_ok=True)
            return 0, False
        if kind == 'report':
            name, *flags = REPORTS[values[0]]
            return self.cli(name, *flags), True
        if kind == 'start':
            return self.cli('start', '--step', values[0]), False
        if kind == 'revalidate':
            return self.cli('start', '--step', values[0], '--revalidate'), False
        if kind in ('verify', 'block'):
            extra = ('--reason', 'interrupted') if kind == 'block' else ()
            return self.cli(kind, '--step', values[0], *extra), False
        if kind == 'assess':
            return self.cli('assess', '--step', 's2', '--check', '1', '--verdict', values[0], '--rationale', 'r'), False
        if kind == 'stop':
            return self.cli('stop', '--reason', values[0]), False
        if kind == 'resume':
            return self.cli('resume', '--rationale', 'user asked to continue'), False
        if kind in ('approve', 'deny'):
            return self.cli(kind, '--step', values[0], '--digest', self.digest_for(values[0]), '--rationale', 'r'), False
        if kind == 'recover':
            return self.cli('recover', '--step', values[0], '--digest', self.recovery_digest(values[0]),
                            '--resolution', values[1], '--rationale', 'r'), False
        if kind == 'review':
            return self.cli('criterion-review', '--criterion', 'A' + values[0], '--verdict', values[1], '--rationale', 'r',
                            '--evidence-ref', 'check:' + values[0] + ':0'), False
        if kind == 'finish':
            return self.cli('finish'), False
        return self.cli('goal-review', '--verdict', values[0], '--rationale', 'r'), False

    def check(self, operation):
        before_bytes = self.path.read_bytes()
        before = self.previous
        code, read_only = self.perform(operation)
        assert code in (0, 1, 2, 3), f'unexpected exit code {code}'
        after_bytes = self.path.read_bytes()
        after = json.loads(after_bytes)
        if read_only or code == 2:
            assert after_bytes == before_bytes, 'exit 2 or a report changed the checkpoint'
        validate_state(after, self.contract)
        assert after['attempts'] >= before['attempts'], 'mission attempts decreased'
        for name, entry in after['steps'].items():
            old = before['steps'].get(name, {})
            assert entry.get('attempts', 0) >= old.get('attempts', 0), 'step attempts decreased'
            if old.get('approval_denied'):
                assert entry.get('approval_denied') and entry.get('status') == 'blocked', 'denial was cleared'
            if entry.get('status') == 'completed':
                assert all(record.get('code') == 0 for record in entry.get('evidence', [])), 'completed with failed evidence'
                assert not entry.get('recovery_required'), 'completed while recovery is required'
        if operation[0] == 'revalidate':
            assert after['attempts'] == before['attempts'], 'revalidation spent an attempt'
        active = [name for name, entry in after['steps'].items() if entry.get('status') == 'in_progress']
        assert len(active) <= 1, 'more than one active step'
        if after.get('stop_reason') == 'done_verified':
            statuses = [after['steps'].get(step['id'], {}).get('status') for step in self.contract['steps']]
            assert statuses == ['completed'] * len(statuses), 'done_verified with incomplete steps'
        if self.contract['schema_version'] == 3:
            grew = len(after['journal']) - len(before['journal'])
            assert grew == int(after_bytes != before_bytes), 'journal did not grow by one per commit'
        self.previous = after


def failure(contract, operations):
    """Return the failing assertion text and operation index, or None if all hold."""
    previous = os.getcwd()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        os.chdir(root)
        try:
            mission = Mission(contract, root)
            for index, operation in enumerate(operations):
                try:
                    mission.check(operation)
                except Exception as error:
                    return f'{type(error).__name__}: {error}', index
        finally:
            os.chdir(previous)
    return None


def minimize(contract, operations):
    """Greedily drop operations while the sequence still fails."""
    current = list(operations)
    index = 0
    while index < len(current):
        candidate = current[:index] + current[index + 1:]
        if failure(contract, candidate):
            current = candidate
        else:
            index += 1
    return current


def helpful_operation(rng, mission):
    """Choose the operation that moves this mission forward, so deep states get exercised."""
    state = mission.load()
    entries = state['steps']
    target = mission.root / 'ok.txt'
    content = target.read_text(encoding='utf-8') if target.exists() else ''
    if state.get('stop_reason') not in (None, 'done_verified'):
        return ('resume',)
    if state.get('stop_reason') == 'done_verified':
        return ('goal', rng.choice(('pass', 'pass', 'fail'))) if 'goal_review' not in state else ('report', 0)
    for step in mission.contract['steps']:
        name = step['id']
        entry = entries.get(name, {})
        status = entry.get('status', 'pending')
        if status == 'in_progress':
            if content != 'good\n':
                return ('good',)
            if name == 's2' and '1' not in entry.get('manual', {}):
                return ('assess', 'pass')
            return ('verify', name)
    for step in mission.contract['steps']:
        name = step['id']
        entry = entries.get(name, {})
        if entry.get('status') == 'awaiting_approval':
            return (rng.choice(('approve', 'approve', 'approve', 'deny')), name)
        if entry.get('recovery_required'):
            return ('recover', name, rng.choice(RESOLUTIONS))
    for step in mission.contract['steps']:
        name = step['id']
        entry = entries.get(name, {})
        status = entry.get('status', 'pending')
        ready = all(entries.get(item, {}).get('status') == 'completed' for item in step.get('depends_on', []))
        if status != 'completed' and ready and not entry.get('approval_denied'):
            return ('revalidate', name) if entry.get('needs_revalidation') else ('start', name)
    reviews = state.get('acceptance_reviews', {})
    if mission.contract['schema_version'] == 3:
        for step in mission.contract['steps']:
            if reviews.get('A' + step['id'], {}).get('verdict') != 'supported':
                return ('review', step['id'], 'supported')
    return ('finish',)


def generate(seed, count=60):
    """Mix guided and random operations; return the contract, trace, failure and final state."""
    rng = random.Random(seed)
    contract = build_contract(rng)
    previous = os.getcwd()
    trace = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        os.chdir(root)
        try:
            mission = Mission(contract, root)
            for _ in range(count):
                operation = (helpful_operation(rng, mission) if rng.random() < 0.8
                             else build_operations(rng, 1)[0])
                trace.append(operation)
                try:
                    mission.check(operation)
                except Exception as error:
                    return contract, trace, f'{type(error).__name__}: {error}', mission.load()
            return contract, trace, None, mission.load()
        finally:
            os.chdir(previous)


def run_seed(seed):
    contract, trace, error, _ = generate(seed)
    if not error:
        return None
    return {'seed': seed, 'error': error, 'operations': minimize(contract, trace),
            'schema': contract['schema_version'], 'mode': contract['mode'], 'budget': contract['budget']}
