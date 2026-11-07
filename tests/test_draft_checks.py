"""New strict drafts catch late failures early, and a revision chain can still be certified."""
import json
from pathlib import Path

from test_draft_in_mission import DraftFixture as DraftBase

ROOT = Path(__file__).resolve().parents[1]
GUIDE = (ROOT / 'references/mission-guide.md').read_text(encoding='utf-8')
DRAFT = '.mission/draft-contract.json'


class DraftChecks(DraftBase):
    def draft(self, change):
        self.repository()
        data = json.loads((ROOT / 'templates/small-fix-contract.json').read_text(encoding='utf-8'))
        change(data['steps'][0])
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        return self.call('validate', '--contract', DRAFT)

    def test_a_check_program_missing_from_path_is_refused_with_an_example(self):
        refused = self.draft(lambda step: step['verify'].append(['exit0', 'build', './...']))
        self.assertEqual(refused.returncode, 2)
        self.assertIn("fix: check program 'build' is not on PATH", refused.stderr)
        self.assertIn('["exit0", "go", "test", "./..."]', refused.stderr)

    def test_a_program_given_as_a_path_is_not_looked_up(self):
        def change(step):
            step['verify'].append(['exit0', './bin/tool', '--version'])
        self.assertEqual(self.draft(change).returncode, 0)

    def test_a_missing_test_first_program_is_refused(self):
        def change(step):
            step['test_first']['command'] = ['pytestx']
            step['verify'] = [['exit0', 'pytestx']]
        refused = self.draft(change)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("check program 'pytestx' is not on PATH", refused.stderr)

    def test_a_directory_watch_is_refused(self):
        (self.work / 'pkg').mkdir()
        refused = self.draft(lambda step: step.update(watch=['pkg']))
        self.assertEqual(refused.returncode, 2)
        self.assertIn('fix: watch takes files, not directories: pkg', refused.stderr)

    def test_a_watch_ending_in_a_slash_is_refused(self):
        refused = self.draft(lambda step: step.update(watch=['later/']))
        self.assertEqual(refused.returncode, 2)
        self.assertIn('watch takes files, not directories: later/', refused.stderr)

    def test_the_guide_shows_a_filled_in_step_and_warns_about_env_files(self):
        self.assertIn('"verify": [["exit0", "go", "test", "./..."]]', GUIDE)
        self.assertIn('env.example', GUIDE)


class RevisionChainGate(DraftBase):
    def setUp(self):
        super().setUp()
        self.repository()
        with open(self.work / '.gitignore', 'a', encoding='utf-8') as handle:
            handle.write('.mission*\n')
        self.git('add', '.gitignore')
        self.git('commit', '-q', '-m', 'ignore missions')
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))

    def revise(self, started):
        if started:
            self.ok('start', '--step', 'fix')
            self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        data = json.loads((self.work / '.mission/contract.json').read_text(encoding='utf-8'))
        data['steps'][0]['description'] = 'Return 2, as the test expects'
        (self.work / '.mission/revised.json').write_text(json.dumps(data), encoding='utf-8')
        self.ok('revise', '--contract', '.mission/revised.json', '--destination', '.mission-r2', '--reason', 'Clarify the step')
        self.ok('init', '--mission', '.mission-r2', '--contract', '.mission-r2/contract.json', '--workspace', str(self.work))
        self.ok('start', '--mission', '.mission-r2', '--step', 'fix')
        self.ok('verify', '--mission', '.mission-r2', '--step', 'fix', '--already-satisfied', '--rationale', 'Done in the parent')
        self.ok('criterion-review', '--mission', '.mission-r2', '--criterion', 'AC-1', '--verdict', 'supported',
                '--rationale', 'The test passes', '--evidence-ref', 'check:fix:0', '--evidence-kind', 'behavior')
        self.ok('finish', '--mission', '.mission-r2')
        self.ok('goal-review', '--mission', '.mission-r2', '--verdict', 'pass', '--rationale', 'Holds')
        self.git('add', 'app.py')
        self.git('commit', '-q', '-m', 'fix')
        return json.loads(self.call('gate', '--mission', '.mission-r2', '--commit', self.git('rev-parse', 'HEAD')).stdout)

    def test_work_started_in_the_parent_mission_is_certified_after_revision(self):
        report = self.revise(started=True)
        self.assertTrue(report['certified'], report['not_certified'])

    def test_work_no_mission_ever_started_is_still_refused(self):
        report = self.revise(started=False)
        self.assertIn('no_change_step_changed_path', {item['reason'] for item in report['not_certified']})
