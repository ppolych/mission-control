"""A stale step after finish reopens alone, red names the scaffolding fix, and finish names unconfirmed red/green."""
import json

from test_draft_in_mission import DraftFixture as DraftBase
from test_stale_revalidation import Fixture, contract


class StaleAfterFinish(Fixture):
    def finished(self):
        data = contract()
        data['steps'][1]['effects']['writes'] = ['more.txt']
        data['steps'][1]['verify'] = [['exit0', 'grep', '-q', 'two', 'more.txt']]
        self.contract_path.write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', str(self.contract_path), '--workspace', str(self.work))
        for step_id, name in (('base', 'app.txt'), ('extend', 'more.txt')):
            self.ok('start', '--step', step_id)
            (self.work / name).write_text('one\ntwo\n', encoding='utf-8')
            self.ok('verify', '--step', step_id)
        for step_id, criterion in (('base', 'AC-1'), ('extend', 'AC-2')):
            self.assertEqual(self.review(criterion, step_id).returncode, 0)
        self.ok('finish')
        self.ok('goal-review', '--verdict', 'pass', '--rationale', 'Both lines are present')

    def checkpoint(self):
        return (self.work / '.mission/state/progress.json').read_bytes()

    def test_a_stale_step_reopens_the_mission_but_only_itself(self):
        self.finished()
        (self.work / 'app.txt').write_text('one\ntwo\nthree\n', encoding='utf-8')
        advice = json.loads(self.ok('status').stdout)['next_action']['argv']
        self.assertEqual(advice[:4], ['start', '--step', 'base', '--revalidate'])
        self.ok('start', '--step', 'base', '--revalidate')
        status = json.loads(self.ok('status').stdout)
        self.assertIsNone(status['stop_reason'])
        self.assertEqual(status['steps']['base']['status'], 'in_progress')
        self.assertEqual(status['steps']['extend']['status'], 'completed')
        self.assertEqual(status['attempts'], 2)
        self.assertEqual(status['goal_review_status'], 'not_applicable')
        self.assertNotIn('goal_review', status)
        self.assertEqual(len(status['goal_review_history']), 1)
        self.ok('verify', '--step', 'base')
        self.assertEqual(self.review('AC-1', 'base').returncode, 0)
        self.ok('finish')
        self.ok('goal-review', '--verdict', 'pass', '--rationale', 'Three lines, rechecked')

    def test_a_current_step_of_a_finished_mission_is_not_reopened(self):
        self.finished()
        before = self.checkpoint()
        refused = self.call('start', '--step', 'base', '--revalidate')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('verification is current', refused.stderr)
        self.assertEqual(self.checkpoint(), before)

    def test_other_step_commands_on_a_finished_mission_explain_the_choices(self):
        self.finished()
        before = self.checkpoint()
        refused = self.call('start', '--step', 'base')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('mission is done_verified', refused.stderr)
        self.assertIn('--revalidate', refused.stderr)
        self.assertIn('resume reopens every step', refused.stderr)
        self.assertEqual(self.checkpoint(), before)

    def test_a_stopped_mission_still_names_its_stop_reason(self):
        self.contract_path.write_text(json.dumps(contract()), encoding='utf-8')
        self.ok('init', '--contract', str(self.contract_path), '--workspace', str(self.work))
        self.ok('stop', '--reason', 'human_paused')
        refused = self.call('start', '--step', 'base')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('resume mission first (stopped as human_paused)', refused.stderr)


class ScaffoldingAndReport(DraftBase):
    def test_red_after_scaffolding_suggests_an_exempt_step(self):
        self.repository()
        self.ok('init', '--contract', '.mission/draft-contract.json', '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 1\n\n', encoding='utf-8')
        refused = self.call('red', '--step', 'fix')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('earlier step with test_first_exempt', refused.stderr)

    def test_finish_and_goal_review_print_unconfirmed_red_green(self):
        self.repository()
        self.ok('init', '--contract', '.mission/draft-contract.json', '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.ok('test-first-note', '--step', 'fix', '--reason', 'Written before the test ran')
        self.ok('verify', '--step', 'fix')
        self.ok('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'The test passes',
                '--evidence-ref', 'check:fix:0', '--evidence-kind', 'behavior')
        line = 'Report in the final message: red/green unconfirmed for fix'
        self.assertIn(line, self.ok('finish').stdout)
        self.assertIn(line, self.ok('goal-review', '--verdict', 'pass', '--rationale', 'Holds').stdout)
