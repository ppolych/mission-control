"""The draft contract lives in the mission root, and the final advisory names unconfirmed red/green."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / 'scripts/mission.py')
SKILL = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
IDENTITY = {'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 't@example.invalid', 'GIT_COMMITTER_NAME': 'Test',
            'GIT_COMMITTER_EMAIL': 't@example.invalid'}
TEST = ('import unittest\nfrom app import value\n\n\nclass T(unittest.TestCase):\n    def test_value(self):\n'
        '        self.assertEqual(value(), 2)\n')
DRAFT = '.mission/draft-contract.json'


class DraftInMissionRoot(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name).resolve() / 'work'
        self.work.mkdir()
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        self.environment.update(IDENTITY)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.work), *args], check=True, capture_output=True, text=True,
                              env=self.environment).stdout.strip()

    def call(self, *args):
        return subprocess.run(['python3', CLI, *args], cwd=self.work, capture_output=True, text=True, env=self.environment)

    def ok(self, *args):
        result = self.call(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def repository(self):
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        (self.work / '.gitignore').write_text('.mission/\n__pycache__/\n', encoding='utf-8')
        (self.work / 'app.py').write_text('def value():\n    return 1\n', encoding='utf-8')
        (self.work / 'test_app.py').write_text(TEST, encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        (self.work / '.mission').mkdir()
        (self.work / DRAFT).write_bytes((ROOT / 'templates/small-fix-contract.json').read_bytes())

    def finish(self):
        self.ok('verify', '--step', 'fix')
        self.ok('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'The test passes',
                '--evidence-ref', 'check:fix:0', '--evidence-kind', 'behavior')
        self.ok('finish')
        return self.ok('goal-review', '--verdict', 'pass', '--rationale', 'Requested behavior holds')

    def test_a_draft_inside_the_mission_root_initializes_and_certifies(self):
        self.repository()
        self.ok('validate', '--contract', DRAFT)
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.assertTrue((self.work / '.mission/contract.json').is_file())
        self.ok('start', '--step', 'fix')
        self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.finish()
        self.git('add', 'app.py')
        self.git('commit', '-q', '-m', 'fix')
        report = json.loads(self.ok('gate', '--commit', self.git('rev-parse', 'HEAD')).stdout)
        self.assertTrue(report['certified'], report)

    def test_a_refused_draft_leaves_the_root_usable_after_the_fix(self):
        self.repository()
        (self.work / DRAFT).write_text(json.dumps({'schema_version': 3}), encoding='utf-8')
        self.assertEqual(self.call('init', '--contract', DRAFT, '--workspace', str(self.work)).returncode, 2)
        self.assertFalse((self.work / '.mission/state').exists())
        (self.work / DRAFT).write_bytes((ROOT / 'templates/small-fix-contract.json').read_bytes())
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))

    def test_the_final_advisory_names_unconfirmed_red_green(self):
        self.repository()
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.ok('test-first-note', '--step', 'fix', '--reason', 'The change was written before the test ran')
        reviewed = self.finish()
        self.assertIn('unconfirmed red/green: fix', reviewed.stderr)
        note = json.loads(self.ok('status').stdout)['next_action']['note']
        self.assertIn('unconfirmed red/green: fix', note)

    def test_the_final_advisory_stays_short_when_red_green_is_confirmed(self):
        self.repository()
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.finish()
        self.assertNotIn('unconfirmed', json.loads(self.ok('status').stdout)['next_action']['note'])


class SkillText(unittest.TestCase):
    def test_the_short_path_drafts_inside_the_mission_root(self):
        section = SKILL.split('## Small changes', 1)[1].split('\n## ', 1)[0]
        self.assertIn('contract=.mission/draft-contract.json', section)
        self.assertNotIn('mktemp', SKILL)

    def test_skill_files_are_read_through_bash(self):
        self.assertIn('read skill files with `cat`', SKILL)

    def test_the_final_report_names_unconfirmed_steps(self):
        self.assertIn('unconfirmed', SKILL.split('## Finish', 1)[1])


if __name__ == '__main__':
    unittest.main()
