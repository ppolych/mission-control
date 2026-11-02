"""Red/green evidence: recorded facts about a failing test, never proof of a good test."""
import json
from pathlib import Path
import unittest

from strict_fixture import StrictFixture

COMMAND = ['python3', '-B', 'check_app.py']
PASSING = "import app\nassert app.VALUE == 2, 'AssertionError: wrong value'\n"


class TestFirstBase(StrictFixture):
    def setUp(self):
        super().setUp()
        del self.step['test_first_exempt']
        self.step['effects']['writes'] = ['app.py', 'check_app.py']
        self.step['verify'] = [['exit0', *COMMAND]]
        self.step['test_first'] = {'command': COMMAND, 'failure_matches': 'wrong value', 'test_paths': ['check_app.py']}
        self.step['verify_timeout'] = 10

    def begin(self):
        self.write('app.py', 'VALUE = 1\n')
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)

    def write_test(self, text=PASSING):
        self.write('check_app.py', text)

    def implement(self):
        self.write('app.py', 'VALUE = 2\n')


class RedCommand(TestFirstBase):
    def test_records_facts_and_no_output(self):
        self.begin()
        self.write_test()
        result = self.call('red', '--step', 'one')
        self.assertEqual(result.returncode, 0, result.stderr)
        record = self.entry()['red']
        self.assertEqual(record['failure_match'], 'matched')
        self.assertEqual(record['exit_status'], 1)
        self.assertNotIn('wrong value', json.dumps(record))
        self.assertEqual(self.entry()['attempts'], 1)

    def test_without_a_pattern_is_marked_exit_only(self):
        del self.step['test_first']['failure_matches']
        self.begin()
        self.write_test()
        self.assertEqual(self.call('red', '--step', 'one').returncode, 0)
        self.assertEqual(self.entry()['red']['failure_match'], 'exit_only')

    def assert_not_red(self, mention):
        result = self.call('red', '--step', 'one')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(mention, result.stderr)
        self.assertNotIn('red', self.entry())

    def test_wrong_failure_reason_is_not_red(self):
        self.begin()
        self.write_test("raise SystemExit('some other failure')\n")
        self.assert_not_red('did not match')

    def test_passing_command_is_not_red(self):
        self.begin()
        self.write_test('')
        self.assert_not_red('passed')

    def test_missing_executable_is_not_red(self):
        self.step['test_first']['command'] = ['definitely-not-installed-xyz']
        self.step['verify'] = [['exit0', 'definitely-not-installed-xyz']]
        self.begin()
        self.write_test()
        self.assert_not_red('could not run')

    def test_exit_127_is_not_red(self):
        command = ['bash', '-c', 'exit 127']
        self.step['test_first']['command'] = command
        self.step['verify'] = [['exit0', *command]]
        del self.step['test_first']['failure_matches']
        self.begin()
        self.write_test()
        self.assert_not_red('could not run')

    def test_timeout_is_not_red(self):
        command = ['sleep', '5']
        self.step['test_first']['command'] = command
        self.step['verify'] = [['exit0', *command]]
        self.step['verify_timeout'] = 0.2
        self.begin()
        self.write_test()
        self.assert_not_red('timed out')

    def test_signal_is_not_red(self):
        command = ['bash', '-c', 'kill -TERM $$']
        self.step['test_first']['command'] = command
        self.step['verify'] = [['exit0', *command]]
        del self.step['test_first']['failure_matches']
        self.begin()
        self.write_test()
        self.assert_not_red('could not run')

    def test_refused_after_implementation_began(self):
        self.begin()
        self.write_test()
        self.implement()
        result = self.call('red', '--step', 'one')
        self.assertEqual(result.returncode, 2)
        self.assertIn('test-first-note', result.stderr)

    def test_needs_the_active_step_and_the_declaration(self):
        self.write('app.py', 'VALUE = 1\n')
        self.init()
        self.assertEqual(self.call('red', '--step', 'one').returncode, 2)

    def test_output_larger_than_a_pipe_does_not_block(self):
        command = ['python3', '-c', "import sys;sys.stdout.write('x'*500000);sys.exit(1)"]
        self.step['test_first'] = {'command': command, 'test_paths': ['check_app.py']}
        self.step['verify'] = [['exit0', *command]]
        self.begin()
        self.write_test()
        self.assertEqual(self.call('red', '--step', 'one').returncode, 0)


class VerifyAfterRed(TestFirstBase):
    def red(self):
        self.begin()
        self.write_test()
        self.assertEqual(self.call('red', '--step', 'one').returncode, 0)

    def test_confirmed_after_red_then_green(self):
        self.red()
        self.implement()
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.entry()['discipline_outcome']['red_green'], 'confirmed')

    def test_verify_needs_red_or_a_note(self):
        self.begin()
        self.write_test()
        self.implement()
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 2)
        self.assertIn('red', result.stderr)

    def test_changed_test_without_note_is_refused(self):
        self.red()
        self.implement()
        self.write_test(PASSING + '# changed\n')
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 2)
        self.assertIn('test-first-note', result.stderr)

    def test_changed_test_with_note_is_unconfirmed_not_reverted(self):
        self.red()
        self.implement()
        self.write_test(PASSING + '# changed\n')
        self.assertEqual(self.call('test-first-note', '--step', 'one', '--reason', 'Assertion was too narrow').returncode, 0)
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = self.entry()['discipline_outcome']
        self.assertEqual(outcome['red_green'], 'unconfirmed')
        self.assertEqual(outcome['test_first_notes'][0]['reason'], 'Assertion was too narrow')
        self.assertEqual((self.root / 'app.py').read_text(encoding='utf-8'), 'VALUE = 2\n')

    def test_implementation_started_first_is_recorded_as_unconfirmed(self):
        self.begin()
        self.write_test()
        self.implement()
        self.assertEqual(self.call('test-first-note', '--step', 'one', '--reason', 'Fix came first').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.entry()['discipline_outcome']['red_green'], 'unconfirmed')

    def test_note_needs_a_reason(self):
        self.begin()
        self.assertEqual(self.call('test-first-note', '--step', 'one').returncode, 2)

    def test_test_fixed_before_implementation_keeps_history_and_can_confirm(self):
        self.begin()
        self.write_test("raise SystemExit('wrong value one')\n")
        self.assertEqual(self.call('red', '--step', 'one').returncode, 0)
        self.write_test()
        self.assertEqual(self.call('red', '--step', 'one').returncode, 0)
        self.assertEqual(len(self.entry()['red_history']), 1)
        self.implement()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.entry()['discipline_outcome']['red_green'], 'confirmed')

    def test_unchanged_implementation_since_red_is_refused(self):
        script = Path(self.root / 'flag')
        command = ['test', '-e', str(script)]
        self.step['test_first'] = {'command': command, 'test_paths': ['check_app.py']}
        self.step['verify'] = [['exit0', *command]]
        self.begin()
        self.write_test()
        self.assertEqual(self.call('red', '--step', 'one').returncode, 0)
        script.write_text('', encoding='utf-8')
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 2)
        self.assertIn('implementation', result.stderr)

    def test_red_survives_a_retry(self):
        self.step['retry'] = 'safe'
        self.red()
        self.write('app.py', 'VALUE = 3\n')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 1)
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.implement()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.entry()['discipline_outcome']['red_green'], 'confirmed')

    def test_no_change_outcome_skips_red(self):
        self.write('app.py', 'VALUE = 2\n')
        self.write_test()
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        result = self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'Already fixed')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.entry()['discipline_outcome']['red_green'], 'not_applicable_no_change')

    def test_next_action_names_red_then_verify(self):
        self.begin()
        report = json.loads(self.call('status').stdout)['next_action']
        self.assertEqual(report['action'], 'red')
        self.assertEqual(report['argv'][:3], ['red', '--step', 'one'])
        self.write_test()
        self.assertEqual(self.call('red', '--step', 'one').returncode, 0)
        self.assertEqual(json.loads(self.call('status').stdout)['next_action']['action'], 'verify')


class DraftShape(TestFirstBase):
    def assert_refused(self):
        code, error = self.validate_error()
        self.assertEqual(code, 2, error)
        self.assertIn('test_first', error)

    def test_valid(self):
        self.assertEqual(self.validate_error()[0], 0)

    def test_command_must_also_be_a_passing_check(self):
        self.step['verify'] = [['file', 'app.py']]
        self.assert_refused()

    def test_paths_must_be_declared_writes(self):
        self.step['test_first']['test_paths'] = ['elsewhere.py']
        self.assert_refused()

    def test_refusal_says_an_existing_test_also_belongs_in_writes(self):
        self.step['test_first']['test_paths'] = ['elsewhere.py']
        self.assertIn('an existing test too', self.validate_error()[1])

    def test_some_write_must_be_implementation(self):
        self.step['test_first']['test_paths'] = ['app.py', 'check_app.py']
        self.assert_refused()

    def test_bad_pattern(self):
        self.step['test_first']['failure_matches'] = '('
        self.assert_refused()

    def test_both_declarations(self):
        self.step['test_first_exempt'] = {'kind': 'docs', 'reason': 'x'}
        self.assert_refused()

    def test_unknown_key_and_empty_values(self):
        for change in ({'extra': 1}, {'command': []}, {'test_paths': []}):
            with self.subTest(change=change):
                value = dict(self.step['test_first'], **change)
                self.step['test_first'] = value
                self.assert_refused()
                self.step['test_first'] = {'command': COMMAND, 'test_paths': ['check_app.py']}

    def test_needs_strict(self):
        del self.data['discipline']
        self.contract.write_text(json.dumps(self.data), encoding='utf-8')
        self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)


if __name__ == '__main__':
    unittest.main()
