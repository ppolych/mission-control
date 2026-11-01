#!/usr/bin/env python3
"""Measure real CLI commands on disposable missions; report median milliseconds."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
# Runs inside the measured installation, so its own journal format is used.
INJECT_JOURNAL = """
import json, sys, types
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from mission_control import journal, storage
path, count = Path(sys.argv[2]), int(sys.argv[3])
state = json.loads(path.read_text())
contract = json.loads((path.parent.parent / 'contract.json').read_text())
real_atomic = storage.atomic
storage.atomic = lambda *_: None
state['journal'] = []
args = types.SimpleNamespace(command='assess', step='s1')
for _ in range(count):
    journal.commit_state(path, state, contract, args)
real_atomic(path, state)
"""


def contract():
    def step(name, depends=()):
        return {'id': name, 'description': name, 'depends_on': list(depends), 'retry': 'safe',
                'verify': [['file', name + '.bin'], {'manual': 'inspect'}], 'acceptance_refs': ['AC-' + name],
                'effects': {'reads': [], 'writes': [name + '.bin'], 'network': 'none',
                            'external_actions': [], 'reversible': True}}
    names = ('s1', 's2', 's3')
    return {'schema_version': 3, 'mission': 'benchmark', 'budget': {'max_attempts_per_step': 1000, 'max_iterations': 100000},
            'steps': [step(name) for name in names],
            'acceptance': [{'id': 'AC-' + name, 'description': name} for name in names]}


class Fixture:
    def __init__(self, cli, root, events, size):
        self.cli = str(cli)
        self.root = root
        self.mission = root / '.mission'
        root.mkdir(parents=True)
        (root / 'contract.json').write_text(json.dumps(contract()))
        self.call('init', '--contract', 'contract.json', '--workspace', str(root))
        for name in ('s1', 's2', 's3'):
            (root / (name + '.bin')).write_bytes(b'x' * size)
            self.call('start', '--step', name)
            self.call('assess', '--step', name, '--check', '1', '--verdict', 'pass', '--rationale', 'benchmark')
            self.call('verify', '--step', name)
            self.call('criterion-review', '--criterion', 'AC-' + name, '--verdict', 'supported', '--rationale', 'benchmark',
                      '--evidence-ref', 'check:' + name + ':1')
        self.inject(events)

    def inject(self, events):
        subprocess.run([sys.executable, '-c', INJECT_JOURNAL, str(Path(self.cli).parent),
                        str(self.mission / 'state/progress.json'), str(events)], check=True)

    def call(self, *args):
        result = subprocess.run([sys.executable, self.cli, *args], cwd=self.root, capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise RuntimeError(' '.join(args) + ': ' + result.stderr[-300:])
        return result


def timed(fixture, args, repeat, restore=False):
    samples = []
    saved = fixture.mission.with_name('.saved')
    if restore:
        shutil.copytree(fixture.mission, saved)
    for _ in range(repeat):
        start = time.perf_counter()
        result = subprocess.run([sys.executable, fixture.cli, *args], cwd=fixture.root, capture_output=True, text=True)
        samples.append((time.perf_counter() - start) * 1000)
        if result.returncode not in (0, 1):
            raise RuntimeError(' '.join(args) + ': ' + result.stderr[-300:])
        if restore:
            shutil.rmtree(fixture.mission)
            shutil.copytree(saved, fixture.mission)
    if restore:
        shutil.rmtree(saved)
    return round(statistics.median(samples), 1)


def measure(cli, events_list, sizes, repeat):
    rows = []
    with tempfile.TemporaryDirectory() as temporary:
        for events in events_list:
            for size in sizes:
                fixture = Fixture(cli, Path(temporary).resolve() / f'{events}-{size}', events, size)
                row = {'events': events, 'file_bytes': size}
                row['version'] = timed(fixture, ['--version'], repeat)
                for name, args in (('status', ['status']), ('handoff', ['handoff', '--compact']),
                                   ('coverage', ['coverage'])):
                    row[name] = timed(fixture, args, repeat)
                row['finish'] = timed(fixture, ['finish'], repeat, restore=True)
                review = ['criterion-review', '--criterion', 'AC-s1', '--verdict', 'supported', '--rationale', 'benchmark',
                          '--evidence-ref', 'check:s1:1']
                row['criterion_review'] = timed(fixture, review, repeat, restore=True)
                rows.append(row)
                print(json.dumps(row), file=sys.stderr)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, default=ROOT / 'scripts/mission.py')
    parser.add_argument('--events', type=int, action='append', help='journal sizes; default 1, 100, 9990')
    parser.add_argument('--bytes', type=int, action='append', help='declared file sizes; default 1 KiB and 1 MiB')
    parser.add_argument('--repeat', type=int, default=7)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = {'scope': 'wall-clock medians on one machine; compare runs only from the same machine',
              'platform': platform.platform(), 'python': platform.python_version(), 'cpus': os.cpu_count(),
              'repeat': args.repeat,
              'rows': measure(args.cli.resolve(), args.events or [1, 100, 9990], args.bytes or [1024, 1024 * 1024], args.repeat)}
    text = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
