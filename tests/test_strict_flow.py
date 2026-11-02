"""End to end from the shipped template: red, green, gate and a real push through the hook."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / 'scripts/mission.py')
IDENTITY = {'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 't@example.invalid', 'GIT_COMMITTER_NAME': 'Test',
            'GIT_COMMITTER_EMAIL': 't@example.invalid'}


class TemplateFlow(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        self.environment.update(IDENTITY, MISSION_PY=CLI, MISSION_DIR=str(self.work / '.mission'))

    def git(self, *args, cwd=None):
        return subprocess.run(['git', '-C', str(cwd or self.work), *args], check=True, capture_output=True, text=True, env=self.environment).stdout.strip()

    def mission(self, *args, code=0):
        result = subprocess.run(['python3', CLI, *args], cwd=self.work, capture_output=True, text=True, env=self.environment)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def test_full_flow(self):
        subprocess.run(['git', 'init', '-q', '--bare', str(self.root / 'remote.git')], check=True)
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        (self.work / '.gitignore').write_text('.mission/\ncontract.json\n__pycache__/\n', encoding='utf-8')
        (self.work / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        self.git('remote', 'add', 'origin', str(self.root / 'remote.git'))
        hook = self.work / '.git/hooks/pre-push'
        shutil.copyfile(ROOT / 'templates/pre-push-gate.sh', hook)
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
        contract = json.loads((ROOT / 'templates/contract.json').read_text(encoding='utf-8'))
        command = ['python3', '-B', 'check_app.py']
        step = contract['steps'][0]
        del step['test_first_exempt']
        step.update(verify=[['exit0', *command]],
                    test_first={'command': command, 'failure_matches': 'wrong value', 'test_paths': ['check_app.py']})
        step['effects']['writes'] = ['app.py', 'check_app.py']
        (self.work / 'contract.json').write_text(json.dumps(contract), encoding='utf-8')
        self.mission('validate', '--contract', 'contract.json')
        self.mission('init', '--contract', 'contract.json', '--workspace', str(self.work))
        self.mission('start', '--step', 'example-001')
        (self.work / 'check_app.py').write_text("import app\nassert app.VALUE == 2, 'wrong value'\n", encoding='utf-8')
        self.mission('red', '--step', 'example-001')
        (self.work / 'app.py').write_text('VALUE = 2\n', encoding='utf-8')
        self.mission('verify', '--step', 'example-001')
        state = json.loads((self.work / '.mission/state/progress.json').read_text(encoding='utf-8'))
        self.assertEqual(state['steps']['example-001']['discipline_outcome']['red_green'], 'confirmed')
        self.mission('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'Checked',
                     '--evidence-ref', 'check:example-001:0', '--evidence-kind', 'content')
        self.mission('finish')
        self.mission('goal-review', '--verdict', 'pass', '--rationale', 'Fix matches the request')
        self.git('add', 'app.py', 'check_app.py')
        self.git('commit', '-q', '-m', 'fix')
        head = self.git('rev-parse', 'HEAD')
        self.assertTrue(json.loads(self.mission('gate', '--commit', head).stdout)['certified'])
        branch = self.git('rev-parse', '--abbrev-ref', 'HEAD')
        self.git('push', '-q', 'origin', branch)
        self.assertEqual(self.git('rev-parse', branch, cwd=self.root / 'remote.git'), head)


if __name__ == '__main__':
    unittest.main()
