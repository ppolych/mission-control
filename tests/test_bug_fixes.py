"""Regressions for defects found by probes and fuzzing in the second project review."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / 'scripts/mission.py')
sys.path.insert(0, str(ROOT / 'scripts'))


def contract(writes=(), checks=(('exit0', 'true'),), **fields):
    step = {'id': 's1', 'description': 'd', 'verify': [list(check) for check in checks], 'acceptance_refs': ['AC-1'],
            'effects': {'reads': [], 'writes': list(writes), 'network': 'none',
                        'external_actions': [], 'reversible': True}}
    data = {'schema_version': 3, 'mission': 'probe', 'steps': [step],
            'acceptance': [{'id': 'AC-1', 'description': 'x'}]}
    data.update(fields)
    return data


class Base(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def call(self, *args, timeout=30, **env):
        return subprocess.run(['python3', CLI, *args], cwd=self.root, capture_output=True, text=True,
                              timeout=timeout, env={**os.environ, **env})

    def init(self, data, *extra):
        (self.root / 'contract.json').write_text(json.dumps(data))
        result = self.call('init', '--contract', 'contract.json', *extra)
        self.assertEqual(result.returncode, 0, result.stderr)

    @property
    def state_path(self):
        return self.root / '.mission/state/progress.json'

    def state(self):
        return json.loads(self.state_path.read_text())

    def digest(self):
        return json.loads(self.call('recovery', '--step', 's1').stdout)['digest']


class SilentSkips(Base):
    def test_impact_reports_a_skipped_oversized_file(self):
        (self.root / 'big.py').write_text('def target():\n    pass\n' + '# filler\n' * 9000)
        report = json.loads(self.call('impact', '--source-root', '.', '--symbol', 'target').stdout)
        self.assertTrue(report['truncated'])
        self.assertEqual(report['skipped_files'], ['big.py'])

    def test_impact_files_examined_never_exceeds_the_limit(self):
        for index in range(70):
            (self.root / f'module{index:02}.py').write_text('x = 1\n')
        report = json.loads(self.call('impact', '--source-root', '.', '--symbol', 'target').stdout)
        self.assertTrue(report['truncated'])
        self.assertEqual(report['files_examined'], 64)

    def test_lessons_search_reports_a_skipped_oversized_file(self):
        (self.root / 'lessons').mkdir()
        (self.root / 'lessons/big.md').write_text('needle\n' * 12000)
        result = self.call('lessons-search', '--lessons-root', 'lessons', '--query', 'needle')
        report = json.loads(result.stdout)
        self.assertTrue(report['truncated'])
        self.assertEqual(report['skipped_files'], ['big.md'])


class RepeatHistory(Base):
    def test_concurrent_records_are_all_kept(self):
        env = {**os.environ, 'NO_PROGRESS_STATE': 'history.json', 'NO_PROGRESS_THRESHOLD': '1000'}
        processes = [subprocess.Popen(['python3', CLI, 'repeat', 'record', 'tool', str(index)], cwd=self.root, env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for index in range(30)]
        errors = [process.communicate()[1] for process in processes]
        self.assertEqual([process.returncode for process in processes], [0] * 30, errors)
        self.assertEqual(len(json.loads((self.root / 'history.json').read_text())), 30)


class UnexpectedErrors(Base):
    def test_deeply_nested_contract_exits_2_without_traceback(self):
        (self.root / 'deep.json').write_text('[' * 200000)
        result = self.call('validate', '--contract', 'deep.json')
        self.assertEqual(result.returncode, 2, result.stderr[-200:])
        self.assertNotIn('Traceback', result.stderr)

    def test_debug_environment_shows_the_traceback(self):
        (self.root / 'deep.json').write_text('[' * 200000)
        result = self.call('validate', '--contract', 'deep.json', MISSION_DEBUG='1')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Traceback', result.stderr)


class CheckpointRecords(Base):
    def schema2(self):
        self.init({'schema_version': 2, 'mission': 'p', 'steps': [{'id': 's1', 'verify': [['exit0', 'true']]}]})
        self.call('start', '--step', 's1')
        self.call('verify', '--step', 's1')

    def test_malformed_records_are_refused_by_every_report(self):
        self.schema2()
        good = self.state()
        for field, value in (('evidence', [1]), ('evidence', [None]), ('history', ['x']), ('recovery_history', [3]),
                             ('effect_baseline', {'f': 'x'}), ('verified_artifacts', {'f': 1}),
                             ('input_baseline', {'f': None})):
            broken = json.loads(json.dumps(good))
            broken['steps']['s1'][field] = value
            self.state_path.write_text(json.dumps(broken))
            for command in ('status', 'handoff', 'metrics', 'diagnose'):
                result = self.call(command)
                self.assertEqual(result.returncode, 2, (field, value, command))
                self.assertNotIn('Traceback', result.stderr)

    def test_nested_history_evidence_is_checked(self):
        self.schema2()
        broken = self.state()
        broken['steps']['s1']['history'] = [{'evidence': ['x'], 'timestamp': 't'}]
        self.state_path.write_text(json.dumps(broken))
        self.assertEqual(self.call('status').returncode, 2)


class MissionRootPlacement(Base):
    def test_init_refuses_a_mission_root_inside_a_declared_output(self):
        (self.root / 'contract.json').write_text(json.dumps(contract(['build'])))
        result = self.call('init', '--mission', 'build/.mission', '--contract', 'contract.json')
        self.assertEqual(result.returncode, 2)
        self.assertIn('mission directory', result.stderr)
        self.assertFalse((self.root / 'build/.mission/state/progress.json').exists())

    def test_init_allows_a_sibling_mission_root(self):
        self.init(contract(['build']))


class AppliedIncorrectEvidence(Base):
    def failed_once(self, **fields):
        self.init(contract(['a.txt'], [('grep', 'good', 'a.txt')], **fields))
        self.call('start', '--step', 's1')
        (self.root / 'a.txt').write_text('bad\n')
        self.assertEqual(self.call('verify', '--step', 's1').returncode, 1)

    def recover(self, resolution):
        return self.call('recover', '--step', 's1', '--digest', self.digest(), '--resolution', resolution,
                         '--rationale', 'inspected')

    def test_old_failure_cannot_justify_a_later_unverified_attempt(self):
        self.failed_once(budget={'max_attempts_per_step': 3, 'no_progress_threshold': 5})
        self.assertEqual(self.recover('not_applied').returncode, 0)
        self.assertEqual(self.call('start', '--step', 's1').returncode, 0)
        self.assertEqual(self.call('block', '--step', 's1', '--reason', 'interrupted').returncode, 0)
        result = self.recover('applied_incorrect')
        self.assertEqual(result.returncode, 2)
        self.assertIn('failed verification', result.stderr)

    def test_failure_survives_resume_after_a_no_progress_stop(self):
        self.failed_once(budget={'max_attempts_per_step': 3, 'no_progress_threshold': 1})
        self.assertEqual(self.state()['stop_reason'], 'no_progress')
        self.assertEqual(self.call('resume').returncode, 0)
        result = self.recover('applied_incorrect')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_start_archives_previous_evidence(self):
        self.failed_once(budget={'max_attempts_per_step': 3, 'no_progress_threshold': 5})
        self.assertEqual(self.recover('not_applied').returncode, 0)
        self.assertEqual(self.call('start', '--step', 's1').returncode, 0)
        entry = self.state()['steps']['s1']
        self.assertEqual(entry['evidence'], [])
        self.assertTrue(any(record.get('evidence') for record in entry['history']))


class AppliedIncorrectNetwork(Base):
    def test_network_effects_are_refused_as_uncertain(self):
        for network in ('external', 'self_hosted'):
            with self.subTest(network=network):
                mission = 'mission-' + network
                data = contract(['a.txt'], [('grep', 'good', 'a.txt')])
                data['steps'][0]['effects']['network'] = network
                (self.root / 'contract.json').write_text(json.dumps(data))
                self.assertEqual(self.call('init', '--mission', mission, '--contract', 'contract.json').returncode, 0)
                self.call('start', '--mission', mission, '--step', 's1')
                (self.root / 'a.txt').write_text('bad\n')
                self.assertEqual(self.call('verify', '--mission', mission, '--step', 's1').returncode, 1)
                report = json.loads(self.call('recovery', '--mission', mission, '--step', 's1').stdout)
                self.assertEqual(report['external_result'], 'unknown')
                result = self.call('recover', '--mission', mission, '--step', 's1', '--digest', report['digest'],
                                   '--resolution', 'applied_incorrect', '--rationale', 'r')
                self.assertEqual(result.returncode, 2)
                self.assertIn('network', result.stderr)
                (self.root / 'a.txt').unlink()


class DirectoryObservationLimit(unittest.TestCase):
    def test_scan_stops_at_the_entry_limit(self):
        from mission_control import observations
        original = os.scandir
        seen = []
        class CountingScan:
            def __init__(self, fd):
                self.inner = original(fd)
            def __enter__(self):
                return self
            def __exit__(self, *details):
                self.inner.close()
            def __iter__(self):
                for item in self.inner:
                    seen.append(item.name)
                    yield item
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'build').mkdir()
            for index in range(20):
                (root / 'build' / str(index)).touch()
            with patch.object(observations, 'MAX_TREE_ENTRIES', 3), patch.object(os, 'scandir', CountingScan):
                value = observations.observe_artifact(str(root), 'build')
        self.assertEqual(value, {'status': 'unavailable', 'reason': 'directory_too_large'})
        self.assertLessEqual(len(seen), 4)


class MutationRunnerInput(unittest.TestCase):
    def test_unknown_mutant_is_refused(self):
        result = subprocess.run([sys.executable, str(ROOT / 'evals/mutation_check.py'), '--only', 'typo_unknown_mutant'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('typo_unknown_mutant', result.stderr)


class StoredContract(Base):
    def test_fifo_contract_is_refused_without_hanging(self):
        self.init(contract())
        stored = self.root / '.mission/contract.json'
        stored.unlink()
        os.mkfifo(stored)
        result = self.call('status', timeout=10)
        self.assertEqual(result.returncode, 2)

    def test_oversized_contract_is_refused(self):
        self.init(contract())
        with (self.root / '.mission/contract.json').open('a') as stream:
            stream.write(' ' * (9 * 1024 * 1024))
        self.assertEqual(self.call('status').returncode, 2)


class RepeatedRefusals(Base):
    def test_exhausted_step_refusal_appends_one_event_only(self):
        data = contract(checks=[('exit0', 'false')], budget={'max_attempts_per_step': 1, 'no_progress_threshold': 9})
        data['steps'][0]['retry'] = 'safe'
        data['steps'].append(dict(data['steps'][0], id='s2', verify=[['exit0', 'true']]))
        self.init(data)
        self.call('start', '--step', 's1')
        self.call('verify', '--step', 's1')
        self.assertEqual(self.call('start', '--step', 's1').returncode, 1)
        before = self.state_path.read_bytes()
        self.assertEqual(self.call('start', '--step', 's1').returncode, 1)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_denied_step_refusal_leaves_the_checkpoint_unchanged(self):
        data = contract(mode='controlled')
        data['steps'][0].update(needs_approval=True, commands=[])
        extra = dict(data['steps'][0], id='s2', acceptance_refs=['AC-1'])
        data['steps'].append(extra)
        self.init(data)
        request = json.loads(self.call('start', '--step', 's1').stdout)
        self.assertEqual(self.call('deny', '--step', 's1', '--digest', request['digest'], '--rationale', 'no').returncode, 1)
        before = self.state_path.read_bytes()
        self.assertEqual(self.call('start', '--step', 's1').returncode, 1)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_max_iterations_stop_refreshes_last_update_in_schema_2(self):
        self.init({'schema_version': 2, 'mission': 'p', 'budget': {'max_iterations': 1},
                   'steps': [{'id': 's1', 'verify': [['exit0', 'false']]}, {'id': 's2', 'verify': [['exit0', 'true']]}]})
        self.call('start', '--step', 's1')
        self.call('verify', '--step', 's1')
        previous = self.state()['last_update']
        self.assertEqual(self.call('start', '--step', 's2').returncode, 1)
        state = self.state()
        self.assertEqual(state['stop_reason'], 'max_iterations')
        self.assertNotEqual(state['last_update'], previous)


class MutatingCommandLocks(Base):
    def replace_lock(self, make):
        self.init(contract())
        lock = self.root / '.mission/.lock'
        lock.unlink()
        make(lock)
        before = self.state_path.read_bytes()
        result = self.call('start', '--step', 's1', timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_symlink_lock_is_refused_and_target_kept(self):
        target = self.root / 'must-stay.txt'
        target.write_text('intact')
        self.replace_lock(lambda lock: lock.symlink_to(target))
        self.assertEqual(target.read_text(), 'intact')

    def test_fifo_lock_is_refused_without_blocking(self):
        self.replace_lock(os.mkfifo)


class DurablePublication(unittest.TestCase):
    def test_atomic_syncs_the_file_and_its_directory(self):
        from mission_control.storage import atomic
        kinds = []
        original = os.fsync
        def record(fd):
            kinds.append(stat.S_ISDIR(os.fstat(fd).st_mode))
            return original(fd)
        with tempfile.TemporaryDirectory() as temporary, patch.object(os, 'fsync', record):
            atomic(Path(temporary) / 'value.json', {'a': 1})
        self.assertIn(False, kinds)
        self.assertEqual(kinds[-1], True)


if __name__ == '__main__':
    unittest.main()
