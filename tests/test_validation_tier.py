"""A passing test command must have run tests: argv decides the tier, output only refines it."""
import json
import sys
from pathlib import Path
import unittest

from test_draft_in_mission import DraftFixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mission_control.validation_tier import grade, is_test_runner, shortfall  # noqa: E402

DRAFT = '.mission/draft-contract.json'
SKIPPED = ('import unittest\n\n\nclass T(unittest.TestCase):\n    @unittest.skip("later")\n'
           '    def test_value(self):\n        pass\n')


def tier(argv, output=''):
    return grade(['exit0', *argv], output)


class Grading(unittest.TestCase):
    def test_runner_summaries_are_counted(self):
        samples = {
            ('go', 'test', './...'): ('ok  \texample.com/a\t0.01s\n?   \texample.com/b\t[no test files]\n', 1),
            ('go', 'test', '-v', './...'): ('--- PASS: TestA (0.00s)\n    --- PASS: TestA/sub (0.00s)\nok  \tx\t0.01s\n', 2),
            ('python3', '-m', 'pytest'): ('===== 4 passed, 1 skipped in 0.12s =====\n', 4),
            ('python3', '-B', '-m', 'unittest'): ('Ran 4 tests in 0.001s\n\nOK (skipped=1)\n', 3),
            ('cargo', 'test'): ('test result: ok. 3 passed; 0 failed; 1 ignored\ntest result: ok. 2 passed; 0 failed\n', 5),
            ('node', '--test'): ('# tests 3\n# pass 3\n# fail 0\n', 3),
            ('npm', 'test'): ('Tests:       3 passed, 3 total\n', 3),
            ('npx', 'vitest', 'run'): ('      Tests  2 passed (2)\n', 2),
            ('npx', 'mocha'): ('\n  2 passing (5ms)\n', 2),
            ('mvn', 'test'): ('[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 1\n', 4),
            ('dotnet', 'test'): ('Passed!  - Failed:     0, Passed:     5, Skipped:     0, Total:     5\n', 5),
        }
        for argv, (output, passed) in samples.items():
            with self.subTest(argv=argv):
                record = tier(argv, output)
                self.assertEqual(record['tier'], 'assertions_executed')
                self.assertEqual(record['passed'], passed)

    def test_a_runner_that_ran_nothing_is_build_only(self):
        for argv, output in ((('go', 'test', '-run', 'Nope', './...'), 'ok  \tx\t0.004s [no tests to run]\n'),
                             (('go', 'test', './none'), '?   \tx\t[no test files]\n'),
                             (('pytest', '-q'), 'no tests ran in 0.01s\n'),
                             (('pytest', '-k', 'zzz'), '===== 3 deselected in 0.01s =====\n'),
                             (('python3', '-m', 'unittest'), 'Ran 0 tests in 0.000s\n\nOK\n')):
            with self.subTest(argv=argv):
                self.assertEqual(tier(argv, output)['tier'], 'build_only')

    def test_an_unreadable_summary_is_unknown_never_a_pass(self):
        record = tier(['npm', 'test'], 'hello\n')
        self.assertEqual(record['tier'], 'unknown')
        self.assertIn('summary could not be read', shortfall(record))
        self.assertIn('ran no tests', shortfall(tier(['pytest'], 'no tests ran in 0.01s\n')))
        self.assertIsNone(shortfall(tier(['pytest'], '1 passed in 0.01s\n')))

    def test_output_cannot_promote_a_command_that_runs_no_tests(self):
        self.assertEqual(tier(['cat', 'README.md'], 'test result: ok. 9 passed; 0 failed')['tier'], 'inspection')
        self.assertEqual(tier(['echo', '--- PASS: TestX'], '--- PASS: TestX')['tier'], 'unknown')
        self.assertEqual(tier(['go', 'build', './...'])['tier'], 'build_only')
        self.assertEqual(grade(['grep', 'x', 'f'], '')['tier'], 'inspection')

    def test_interpreter_flags_before_the_module_are_skipped(self):
        self.assertTrue(is_test_runner(['python3', '-B', '-m', 'unittest']))
        self.assertFalse(is_test_runner(['python3', '-B', 'check_app.py']))
        self.assertFalse(is_test_runner(['python3', '-c', 'import unittest']))


class CountedTests(DraftFixture):
    def begin(self):
        self.repository()
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')

    def test_a_plain_script_test_command_is_refused_while_drafting(self):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        data['steps'][0]['test_first']['command'] = ['python3', '-B', 'check.py']
        data['steps'][0]['verify'] = [['exit0', 'python3', '-B', 'check.py']]
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        refused = self.call('validate', '--contract', DRAFT)
        self.assertEqual(refused.returncode, 2)
        self.assertIn('is not a test runner whose tests verify can count', refused.stderr)
        self.assertIn('uncounted_reason', refused.stderr)

    def test_verify_records_the_tests_that_ran(self):
        self.begin()
        self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        verified = self.ok('verify', '--step', 'fix')
        self.assertIn('PASS: exit0 (check 0, python3: 1 tests passed)', verified.stdout)
        outcome = json.loads(self.ok('status').stdout)['steps']['fix']['discipline_outcome']
        self.assertEqual(outcome['tests']['tier'], 'assertions_executed')
        self.assertEqual(outcome['tests']['passed'], 1)

    def test_a_suite_that_ran_no_tests_fails_verify(self):
        self.begin()
        (self.work / 'test_app.py').write_text(SKIPPED, encoding='utf-8')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.ok('test-first-note', '--step', 'fix', '--reason', 'The test is skipped on purpose here')
        refused = self.call('verify', '--step', 'fix')
        self.assertEqual(refused.returncode, 1)
        self.assertIn('FAIL: exit0 (check 0, python3 ran no tests)', refused.stdout)
        self.assertIn('passed but ran no tests', refused.stdout)
        self.assertNotEqual(json.loads(self.ok('status').stdout)['steps']['fix']['status'], 'completed')

    def test_an_uncounted_runner_is_named_in_the_final_report(self):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        command = ['python3', '-B', 'test_app.py']
        data['steps'][0]['test_first'].update(command=command, uncounted_reason='A script without a runner summary')
        data['steps'][0]['verify'] = [['exit0', *command]]
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        (self.work / 'test_app.py').write_text('from app import value\nassert value() == 2\n', encoding='utf-8')
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.ok('verify', '--step', 'fix')
        self.ok('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'The script passes',
                '--evidence-ref', 'check:fix:0', '--evidence-kind', 'behavior')
        self.assertIn('tests were not counted for fix', self.ok('finish').stdout)

    def test_init_records_the_controller(self):
        self.begin()
        controller = json.loads(self.ok('status').stdout)['controller']
        self.assertEqual(set(controller), {'version', 'engine_fingerprint'})


if __name__ == '__main__':
    unittest.main()
