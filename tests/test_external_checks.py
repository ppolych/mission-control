"""Strict drafts refuse a check that repeats an external action, and finished missions name the gate."""
import json
from pathlib import Path
import sys
import unittest

from strict_fixture import StrictFixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from mission_control.discipline import validate_discipline  # noqa: E402

PUSH = ['git', 'push', 'origin', 'main']


class RepeatedExternalAction(StrictFixture):
    def setUp(self):
        super().setUp()
        self.step['effects'].update(writes=[], external_actions=['git push origin main'], reversible=False)
        self.step.pop('test_first_exempt')
        self.step['retry'] = 'inspect'

    def assert_refused(self):
        code, error = self.validate_error()
        self.assertEqual(code, 2, error)
        self.assertIn('repeats an external action', error)

    def test_argv_check_matching_a_declared_action(self):
        self.step['verify'] = [['exit0', *PUSH]]
        self.assert_refused()

    def test_script_check_matching_a_declared_action(self):
        self.step['verify'] = [['exec', ' git push origin main ']]
        self.assert_refused()

    def test_check_matching_a_declared_command_when_action_text_differs(self):
        self.step['effects']['external_actions'] = ['Publish the fix to the local remote']
        self.step['commands'] = [PUSH]
        self.step['verify'] = [['exit0', *PUSH]]
        self.assert_refused()

    def test_irreversible_step_counts_without_a_named_action(self):
        self.step['effects']['external_actions'] = []
        self.step['commands'] = [PUSH]
        self.step['verify'] = [['exit0', *PUSH]]
        self.assert_refused()

    def test_network_step_counts_while_reversible(self):
        self.step['effects'].update(external_actions=[], reversible=True, network='external')
        self.step['commands'] = [PUSH]
        self.step['verify'] = [['exit0', *PUSH]]
        self.assert_refused()

    def test_init_also_refuses_and_publishes_nothing(self):
        self.step['verify'] = [['exit0', *PUSH]]
        self.contract.write_text(json.dumps(self.data), encoding='utf-8')
        result = self.call('init', '--contract', str(self.contract), '--workspace', str(self.root))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('repeats an external action', result.stderr)
        self.assertFalse((self.mission / 'state/progress.json').exists())

    def test_read_only_check_of_the_action_is_valid(self):
        self.step['commands'] = [PUSH]
        self.step['verify'] = [['exit0', 'git', 'ls-remote', 'origin', 'main']]
        self.assertEqual(self.validate_error()[0], 0)

    def test_reversible_local_command_may_be_its_own_check(self):
        command = ['python3', '-m', 'unittest']
        self.step['effects'].update(external_actions=[], reversible=True)
        self.step['commands'] = [command]
        self.step['verify'] = [['exit0', *command]]
        self.assertEqual(self.validate_error()[0], 0)

    def test_contract_without_discipline_keeps_its_behavior(self):
        del self.data['discipline']
        self.step['verify'] = [['exit0', *PUSH]]
        self.assertEqual(self.validate_error()[0], 0)

    def test_frozen_contract_check_does_not_apply_the_draft_rule(self):
        self.step['verify'] = [['exit0', *PUSH]]
        validate_discipline(self.data)


class GateHint(StrictFixture):
    def finish_mission(self, verdict='pass'):
        self.step['verify'] = [['file', 'out.txt']]
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.write()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.call('finish').returncode, 0)
        return self.call('goal-review', '--verdict', verdict, '--rationale', 'compared')

    def next(self):
        return json.loads(self.call('status').stdout)['next_action']

    def test_passing_goal_review_names_gate_before_push(self):
        result = self.finish_mission()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gate --commit', result.stderr)
        report = self.next()
        self.assertEqual((report['action'], report['argv']), ('report_outcome', []))
        self.assertIn('gate --commit', report['note'])

    def test_failed_goal_review_does_not_name_gate(self):
        self.finish_mission('fail')
        self.assertNotIn('gate --commit', self.next()['note'])


class GateHintWithoutDiscipline(StrictFixture):
    def test_note_is_unchanged(self):
        del self.data['discipline']
        del self.step['test_first_exempt']
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.write()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.call('finish').returncode, 0)
        self.assertEqual(self.call('goal-review', '--verdict', 'pass', '--rationale', 'met').returncode, 0)
        self.assertNotIn('gate --commit', json.loads(self.call('status').stdout)['next_action']['note'])


if __name__ == '__main__':
    unittest.main()
