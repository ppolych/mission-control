"""One small change through the shipped short path, and the rule that naming the skill requires the mission."""
import json
import os
from pathlib import Path
import re
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


class ShortPath(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        self.environment.update(IDENTITY)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.work), *args], check=True, capture_output=True, text=True,
                              env=self.environment).stdout.strip()

    def mission(self, *args):
        result = subprocess.run(['python3', CLI, *args], cwd=self.work, capture_output=True, text=True, env=self.environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_template_runs_from_red_to_a_certified_commit(self):
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        (self.work / '.gitignore').write_text('.mission/\n__pycache__/\n', encoding='utf-8')
        (self.work / 'app.py').write_text('def value():\n    return 1\n', encoding='utf-8')
        (self.work / 'test_app.py').write_text(TEST, encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        contract = str(self.root / 'contract.json')
        Path(contract).write_bytes((ROOT / 'templates/small-fix-contract.json').read_bytes())
        self.mission('validate', '--contract', contract)
        self.mission('init', '--contract', contract, '--workspace', str(self.work))
        self.mission('start', '--step', 'fix')
        self.mission('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.mission('verify', '--step', 'fix')
        self.mission('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'The test now passes',
                     '--evidence-ref', 'check:fix:0', '--evidence-kind', 'behavior')
        self.mission('finish')
        self.mission('goal-review', '--verdict', 'pass', '--rationale', 'Requested behavior holds')
        self.git('add', 'app.py')
        self.git('commit', '-q', '-m', 'fix')
        report = json.loads(self.mission('gate', '--commit', self.git('rev-parse', 'HEAD')).stdout)
        self.assertTrue(report['certified'], report)
        status = json.loads(self.mission('status').stdout)
        self.assertEqual(status['steps']['fix']['discipline_outcome']['red_green'], 'confirmed')

    def test_every_command_of_the_template_flow_is_in_the_skill(self):
        section = SKILL.split('## Small changes', 1)[1].split('\n## ', 1)[0]
        for name in ('validate', 'init', 'start', 'red', 'verify', 'criterion-review', 'finish', 'goal-review', 'gate'):
            self.assertRegex(section, r'"\$M" ' + name + r'\b')
        self.assertIn('templates/small-fix-contract.json', section)

    def test_new_function_fails_with_an_import_error_and_still_records_red(self):
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        (self.work / '.gitignore').write_text('.mission/\n__pycache__/\n', encoding='utf-8')
        (self.work / 'app.py').write_text('', encoding='utf-8')
        (self.work / 'test_app.py').write_text(TEST, encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        contract = str(self.root / 'contract.json')
        Path(contract).write_bytes((ROOT / 'templates/small-fix-contract.json').read_bytes())
        self.mission('init', '--contract', contract, '--workspace', str(self.work))
        self.mission('start', '--step', 'fix')
        self.mission('red', '--step', 'fix')
        status = json.loads((self.work / '.mission/state/progress.json').read_text(encoding='utf-8'))
        self.assertEqual(status['steps']['fix']['red']['failure_match'], 'exit_only')

    def test_mismatch_refusal_names_the_way_forward_and_keeps_the_mission(self):
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        (self.work / '.gitignore').write_text('.mission/\n__pycache__/\n', encoding='utf-8')
        (self.work / 'app.py').write_text('', encoding='utf-8')
        (self.work / 'test_app.py').write_text(TEST, encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        document = json.loads((ROOT / 'templates/small-fix-contract.json').read_text(encoding='utf-8'))
        document['steps'][0]['test_first']['failure_matches'] = 'AssertionError'
        contract = self.root / 'contract.json'
        contract.write_text(json.dumps(document), encoding='utf-8')
        self.mission('init', '--contract', str(contract), '--workspace', str(self.work))
        self.mission('start', '--step', 'fix')
        result = subprocess.run(['python3', CLI, 'red', '--step', 'fix'], cwd=self.work, capture_output=True, text=True, env=self.environment)
        self.assertEqual(result.returncode, 1, result.stderr)
        for phrase in ('test-first-note', 'revise', 'Do not delete'):
            self.assertIn(phrase, result.stderr)
        self.assertTrue((self.work / '.mission/state/progress.json').exists())


class NamedSkillRule(unittest.TestCase):
    def test_mission_root_is_kept_and_refusals_are_reported(self):
        section = ' '.join(SKILL.split('## Activate the controller', 1)[1].split('\n## ', 1)[0].split())
        self.assertIn('Never delete the mission root', section)
        self.assertIn('Report every refusal', section)

    def test_description_applies_when_named_and_no_longer_excludes_it(self):
        description = re.search(r'^description: (.+)$', SKILL, re.M).group(1)
        self.assertIn('by name', description)
        self.assertIn('Otherwise exclude simple edits', description)

    def test_activation_rule_covers_urgency_and_refusal(self):
        section = SKILL.split('## Activate the controller', 1)[1].split('\n## ', 1)[0]
        text = ' '.join(section.split())
        self.assertIn('asks for this skill by name', text)
        self.assertIn('Urgency', text)
        self.assertIn('before the first project change', text)


class WindowsHostPath(unittest.TestCase):
    def test_skill_converts_the_path_and_forbids_searching_for_it(self):
        text = ' '.join(SKILL.split('## Command path', 1)[1].split('```', 1)[0].split())
        self.assertIn("SKILL=$(wslpath -u '", text)
        self.assertIn('never search', text.lower())
        self.assertIn('find /', text)

    def test_wsl_guide_says_the_same(self):
        guide = (ROOT / 'references/wsl.md').read_text(encoding='utf-8')
        self.assertIn('wslpath -u', guide.split('## Locate the skill', 1)[1])
        self.assertIn('find /', guide)


if __name__ == '__main__':
    unittest.main()
