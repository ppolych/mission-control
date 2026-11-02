"""The controller names the next lifecycle command; the hint grants nothing."""
import json
import unittest

import test_controlled as fixtures
from v3_fixture import V3Fixture


class NextActionFlow(V3Fixture):
    def next(self):
        result = self.call('status')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['next_action']

    def assert_next(self, action, *argv):
        report = self.next()
        self.assertEqual(report['action'], action, report)
        self.assertEqual(report['argv'][:len(argv)], list(argv))
        self.assertTrue(report['advisory'])
        self.assertFalse(report['retry_authorized'])
        return report

    def test_walks_the_whole_lifecycle(self):
        self.data['steps'][0]['verify'] = [['exit0', 'true'], {'manual': 'inspect'}]
        self.init()
        self.assert_next('start', 'start', '--step', 'one')
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        report = self.assert_next('assess', 'assess', '--step', 'one', '--check', '1')
        self.assertIn('--verdict', report['argv'])
        self.assertEqual(self.call('assess', '--step', 'one', '--check', '1', '--verdict', 'pass',
                                   '--rationale', 'inspected').returncode, 0)
        self.assert_next('verify', 'verify', '--step', 'one')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assert_next('criterion_review', 'criterion-review', '--criterion', 'AC-1')
        self.assertEqual(self.review().returncode, 0)
        self.assert_next('finish', 'finish')
        self.assertEqual(self.call('finish').returncode, 0)
        self.assert_next('goal_review', 'goal-review')
        self.assertEqual(self.call('goal-review', '--verdict', 'pass', '--rationale', 'met').returncode, 0)
        report = self.assert_next('report_outcome')
        self.assertEqual(report['argv'], [])

    def test_approval_wait_needs_the_user(self):
        self.data.update(mode='controlled')
        self.data['steps'][0]['needs_approval'] = True
        self.init()
        request = self.gate()
        report = self.assert_next('wait_for_user_decision', 'approve', '--step', 'one', '--digest', request['digest'])
        self.assertTrue(report['requires_user'])

    def test_denied_only_work_asks_the_user_and_offers_no_command(self):
        self.data.update(mode='controlled')
        self.data['steps'][0]['needs_approval'] = True
        self.init()
        self.assertEqual(self.decide('deny').returncode, 1)
        report = self.next()
        self.assertTrue(report['requires_user'])
        self.assertEqual(report['argv'], [])

    def test_stopped_mission_offers_no_command(self):
        self.init()
        self.assertEqual(self.call('stop', '--reason', 'human_paused').returncode, 0)
        report = self.assert_next('inspect_stop_reason')
        self.assertEqual(report['argv'], [])
        self.assertTrue(report['requires_user'])

    def test_interrupted_inspect_step_points_to_recovery(self):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.assertEqual(self.call('stop', '--reason', 'human_paused').returncode, 0)
        self.assertEqual(self.call('resume').returncode, 0)
        self.assert_next('inspect_recovery', 'recovery', '--step', 'one')

    def test_revalidation_is_named_after_a_resume(self):
        self.init()
        self.complete()
        self.assertEqual(self.call('stop', '--reason', 'human_paused').returncode, 0)
        self.assertEqual(self.call('resume').returncode, 0)
        report = self.assert_next('revalidate', 'start', '--step', 'one')
        self.assertIn('--revalidate', report['argv'])

    def test_dependency_order_picks_the_ready_step(self):
        second = dict(self.data['steps'][0], id='two', depends_on=['one'])
        self.data['steps'] = [second, self.data['steps'][0]]
        self.init()
        self.assert_next('start', 'start', '--step', 'one')

    def test_selected_mission_directory_is_part_of_the_command(self):
        self.init()
        argv = self.next()['argv']
        self.assertEqual(argv[-2:], ['--mission', str(self.mission)])

    def test_status_does_not_change_the_checkpoint(self):
        self.init()
        path = self.mission / 'state/progress.json'
        before = path.read_bytes()
        self.next()
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn('next_action', self.state())


class NextActionReports(V3Fixture):
    def test_handoff_and_compact_handoff_carry_it(self):
        self.init()
        for args in (('handoff',), ('handoff', '--compact')):
            report = json.loads(self.call(*args).stdout)
            self.assertEqual(report['next_action']['action'], 'start', args)

    def test_diagnose_carries_it(self):
        self.init()
        self.assertEqual(json.loads(self.call('diagnose').stdout)['next_action']['action'], 'start')

    def test_mutating_command_prints_the_hint_on_stderr_only(self):
        self.init()
        result = self.call('start', '--step', 'one')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('next (advisory): ', result.stderr)
        self.assertIn('verify --step one', result.stderr)

    def test_failed_verification_still_names_a_next_step(self):
        self.data['steps'][0]['verify'] = [['exit0', 'false']]
        self.data['steps'][0]['retry'] = 'safe'
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 1)
        self.assertIn('next (advisory): ', result.stderr)


class SchemaTwo(unittest.TestCase):
    setUp = fixtures.ControlledMode.setUp
    call = fixtures.ControlledMode.call
    init = fixtures.ControlledMode.init

    def test_schema_two_finishes_without_criterion_reviews(self):
        self.data.update(mode='autonomous')
        self.data['steps'][0].update(risk='low')
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        report = json.loads(self.call('status').stdout)['next_action']
        self.assertEqual(report['action'], 'finish')


if __name__ == '__main__':
    unittest.main()
