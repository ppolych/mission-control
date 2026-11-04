"""A later step that changes an earlier step's files, and init failures that leave nothing behind."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / 'scripts/mission.py')


def step(identifier, writes, check, depends_on=(), criterion=None):
    return {'id': identifier, 'description': 'Write ' + ', '.join(writes), 'depends_on': list(depends_on),
            'verify': [check], 'risk': 'low', 'needs_approval': False, 'commands': [],
            'acceptance_refs': [criterion], 'watch': [], 'retry': 'inspect',
            'effects': {'reads': [], 'writes': list(writes), 'network': 'none', 'external_actions': [], 'reversible': True}}


def contract(strict=False):
    data = {'schema_version': 3, 'mission': 'Build a file in two steps', 'constraints': [], 'mode': 'autonomous',
            'steps': [step('base', ['app.txt'], ['file', 'app.txt'], criterion='AC-1'),
                      step('extend', ['app.txt'], ['exit0', 'grep', '-q', 'two', 'app.txt'], ['base'], 'AC-2')],
            'acceptance': [{'id': 'AC-1', 'description': 'The file exists'},
                           {'id': 'AC-2', 'description': 'The file has the second line'}],
            'allowed_paths': ['.']}
    if strict:
        data['discipline'] = 'strict'
        for item in data['steps']:
            item['test_first_exempt'] = {'kind': 'docs', 'reason': 'A text file with no behavior to test'}
    return data


class Fixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.contract_path = self.root / 'contract.json'

    def call(self, *args):
        return subprocess.run(['python3', CLI, *args], cwd=self.work, capture_output=True, text=True,
                              env={**os.environ, 'NO_PROGRESS_STATE': str(self.root / 'repeat')})

    def ok(self, *args):
        result = self.call(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def review(self, criterion, step_id):
        return self.call('criterion-review', '--criterion', criterion, '--verdict', 'supported', '--rationale',
                         'Checked the file', '--evidence-ref', 'check:' + step_id + ':0')

    def build_with_stale_base(self, strict=False):
        self.contract_path.write_text(json.dumps(contract(strict)), encoding='utf-8')
        self.ok('init', '--contract', str(self.contract_path), '--workspace', str(self.work))
        self.ok('start', '--step', 'base')
        (self.work / 'app.txt').write_text('one\n', encoding='utf-8')
        self.ok('verify', '--step', 'base')
        self.assertEqual(self.review('AC-1', 'base').returncode, 0)
        self.ok('start', '--step', 'extend')
        (self.work / 'app.txt').write_text('one\ntwo\n', encoding='utf-8')
        self.ok('verify', '--step', 'extend')
        self.assertEqual(self.review('AC-2', 'extend').returncode, 0)

    def coverage(self):
        rows = json.loads(self.ok('coverage').stdout)['criteria']
        return {row['id']: (row['status'], row['stale']) for row in rows}


class StaleCompletedStep(Fixture):
    def test_finish_names_the_stale_step_and_the_command_that_refreshes_it(self):
        self.build_with_stale_base()
        self.assertEqual(self.coverage()['AC-1'], ('unverified', True))
        refused = self.call('finish')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('stale steps: base', refused.stderr)
        self.assertIn('start --step base --revalidate', refused.stderr)

    def assert_revalidation_refreshes(self, strict):
        self.build_with_stale_base(strict)
        self.ok('start', '--step', 'base', '--revalidate')
        status = json.loads(self.ok('status').stdout)
        self.assertEqual(status['steps']['base']['status'], 'in_progress')
        self.assertEqual(status['steps']['extend']['status'], 'completed')
        self.assertEqual(status['attempts'], 2, 'revalidation spends no attempt')
        self.ok('verify', '--step', 'base')
        self.assertEqual(self.review('AC-1', 'base').returncode, 0)
        self.assertEqual(self.coverage(), {'AC-1': ('supported', False), 'AC-2': ('supported', False)})
        self.ok('finish')

    def test_revalidating_the_stale_step_alone_lets_the_mission_finish(self):
        self.assert_revalidation_refreshes(strict=False)

    def test_revalidation_of_a_stale_step_works_in_a_strict_mission(self):
        self.assert_revalidation_refreshes(strict=True)

    def test_the_advisory_names_the_stale_step_once_every_step_is_complete(self):
        self.build_with_stale_base()
        report = json.loads(self.ok('status').stdout)['next_action']
        self.assertEqual(report['argv'][:4], ['start', '--step', 'base', '--revalidate'])

    def test_a_current_completed_step_still_refuses_revalidation(self):
        self.build_with_stale_base()
        before = (self.work / '.mission/state/progress.json').read_bytes()
        refused = self.call('start', '--step', 'extend', '--revalidate')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('verification is current', refused.stderr)
        self.assertEqual((self.work / '.mission/state/progress.json').read_bytes(), before)

    def test_revalidation_waits_while_another_step_is_active(self):
        self.contract_path.write_text(json.dumps(contract()), encoding='utf-8')
        self.ok('init', '--contract', str(self.contract_path), '--workspace', str(self.work))
        self.ok('start', '--step', 'base')
        (self.work / 'app.txt').write_text('one\n', encoding='utf-8')
        self.ok('verify', '--step', 'base')
        self.ok('start', '--step', 'extend')
        (self.work / 'app.txt').write_text('one\ntwo\n', encoding='utf-8')
        refused = self.call('start', '--step', 'base', '--revalidate')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('another step active', refused.stderr)

    def test_the_criterion_review_refusal_names_the_revalidation_command(self):
        self.build_with_stale_base()
        refused = self.review('AC-1', 'base')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('start --step base --revalidate', refused.stderr)


class InitLeavesNothingBehind(Fixture):
    def test_a_missing_contract_creates_no_mission_directory(self):
        refused = self.call('init', '--mission', '.mission-r2', '--contract', '.mission-r2/contract.json',
                            '--workspace', str(self.work))
        self.assertEqual(refused.returncode, 2)
        self.assertFalse(os.path.lexists(self.work / '.mission-r2'))

    def test_an_invalid_contract_creates_no_mission_directory(self):
        self.contract_path.write_text(json.dumps({'schema_version': 3}), encoding='utf-8')
        refused = self.call('init', '--contract', str(self.contract_path), '--workspace', str(self.work))
        self.assertEqual(refused.returncode, 2)
        self.assertFalse(os.path.lexists(self.work / '.mission'))

    def test_a_declared_write_inside_the_mission_root_is_refused_before_anything_is_created(self):
        data = contract()
        data['steps'][0]['effects']['writes'] = ['.mission/state/progress.json']
        data['steps'][0]['verify'] = [['file', '.mission/state/progress.json']]
        self.contract_path.write_text(json.dumps(data), encoding='utf-8')
        refused = self.call('init', '--contract', str(self.contract_path), '--workspace', str(self.work))
        self.assertEqual(refused.returncode, 2)
        self.assertIn('inside the mission directory', refused.stderr)
        self.assertFalse(os.path.lexists(self.work / '.mission'))


if __name__ == '__main__':
    unittest.main()
