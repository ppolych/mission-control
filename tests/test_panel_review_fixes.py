"""Regressions for the independent review of 0.4.2.13: each test names the finding it pins."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from test_acceptance_panel import CLEAN, PanelFixture
from test_draft_in_mission import DraftFixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from mission_control.checks import run_captured  # noqa: E402
from mission_control.panel import parse_review, validate_records  # noqa: E402
from mission_control.validation_tier import TAIL_BYTES, grade  # noqa: E402

DRAFT = '.mission/draft-contract.json'


def tier(argv, output=''):
    return grade(['exit0', *argv], output)['tier']


class GradingFixes(unittest.TestCase):
    def test_go_commands_that_run_no_tests_are_build_only(self):
        for argv in (('go', 'test', '-list', '.', './...'), ('go', 'test', '-c', './x'), ('go', 'test', '-run', '^$', '-bench', '.')):
            with self.subTest(argv=argv):
                self.assertEqual(tier(argv, 'ok  \tx\t0.01s\n'), 'build_only')

    def test_only_the_named_runners_summary_is_read(self):
        output = 'test result: ok. 3 passed; 0 failed\nno tests ran in 0.01s\n'
        self.assertEqual(tier(['pytest'], output), 'build_only')
        self.assertEqual(tier(['python3', '-m', 'unittest'], 'test result: ok. 3 passed; 0 failed\n'), 'unknown')

    def test_more_runner_forms_are_counted(self):
        self.assertEqual(tier(['cargo', 'nextest', 'run'], '     Summary [   0.1s] 5 tests run: 5 passed, 0 skipped\n'),
                         'assertions_executed')
        self.assertEqual(tier(['pytest'], '===== 2 xfailed in 0.10s =====\n'), 'assertions_executed')
        self.assertEqual(tier(['python3', '-X', 'dev', '-m', 'pytest'], '1 passed in 0.01s\n'), 'assertions_executed')

    def test_captured_output_keeps_only_a_bounded_tail(self):
        script = "import sys; sys.stdout.write('x' * 3000000); print(); print('Ran 1 test in 0.1s')"
        status, output = run_captured(['python3', '-c', script], None, 30)
        self.assertEqual(status, 0)
        self.assertLessEqual(len(output.encode()), TAIL_BYTES)
        self.assertTrue(output.rstrip().endswith('Ran 1 test in 0.1s'))


class RecordFixes(unittest.TestCase):
    def test_malformed_records_are_refused_not_crashed(self):
        for panel in ({'votes': [{}], 'reviews': []},
                      {'votes': [], 'reviews': [{'work_digest': 'a', 'reply_digest': 'b', 'timestamp': 't', 'status': 'parsed',
                                                 'findings': [{'title': 'x', 'priority': 'high'}]}]},
                      {'votes': []}):
            with self.subTest(panel=panel):
                with self.assertRaisesRegex(ValueError, 'invalid acceptance panel record'):
                    validate_records(panel)

    def test_deeply_nested_json_is_inconclusive(self):
        self.assertEqual(parse_review('{"a":' * 5000 + '1' + '}' * 5000)['status'], 'inconclusive')


class PanelFixes(PanelFixture):
    def test_the_same_reply_counts_once(self):
        self.finished()
        for _ in range(3):
            self.reply('skeptic-record', 'VERDICT: NOT_REFUTED')
        self.reply('review-record', CLEAN)
        self.assertIn('2 more skeptic vote(s) on the current work, each a different reply', self.pass_review().stderr)

    def test_a_review_calling_the_work_incorrect_is_not_clean(self):
        self.finished()
        for index in range(3):
            self.reply('skeptic-record', 'Vote ' + str(index) + '\nVERDICT: NOT_REFUTED')
        self.reply('review-record', json.dumps({'findings': [], 'overall_correctness': 'patch is incorrect',
                                                'overall_explanation': 'Wrong.'}))
        self.assertIn('a review that does not call the work incorrect', self.pass_review().stderr)


class ContractFixes(DraftFixture):
    def test_a_panel_without_strict_discipline_is_refused(self):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        del data['discipline']
        for step in data['steps']:
            step.pop('test_first', None)
        data['acceptance_panel'] = {'mode': 'bogus', 'skeptics': 99}
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        refused = self.call('validate', '--contract', DRAFT)
        self.assertEqual(refused.returncode, 2)
        self.assertIn('acceptance_panel requires discipline: strict', refused.stderr)

    def test_a_go_test_first_without_v_is_refused(self):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        data['steps'][0]['test_first']['command'] = ['go', 'test', './...']
        data['steps'][0]['verify'] = [['exit0', 'go', 'test', './...']]
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        if shutil.which('go') is None:
            self.skipTest('go is not installed, so the PATH check refuses first')
        self.assertIn('needs -v or -json', self.call('validate', '--contract', DRAFT).stderr)

    def test_revise_is_refused_after_the_controller_changed(self):
        install = self.work.parent / 'skill'
        shutil.copytree(ROOT / 'scripts', install / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy(ROOT / 'VERSION', install / 'VERSION')
        self.repository()
        cli = ['python3', str(install / 'scripts/mission.py')]
        run = lambda *args: subprocess.run([*cli, *args], cwd=self.work, capture_output=True, text=True, env=self.environment)
        self.assertEqual(run('init', '--contract', DRAFT, '--workspace', str(self.work)).returncode, 0)
        module = install / 'scripts/mission_control/test_first.py'
        module.write_text(module.read_text(encoding='utf-8') + '\n# edited\n', encoding='utf-8')
        (self.work / '.mission/revised.json').write_text((self.work / '.mission/contract.json').read_text(encoding='utf-8'),
                                                        encoding='utf-8')
        refused = run('revise', '--contract', '.mission/revised.json', '--destination', '.mission-r2', '--reason', 'More')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('controller changed since this mission began', refused.stderr)
