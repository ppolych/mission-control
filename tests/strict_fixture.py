"""A disposable strict-discipline mission writing one declared file."""
import json
from pathlib import Path
import subprocess

from v3_fixture import V3Fixture

CLEAN_GIT_ENV = {'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',
                 'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid'}


class StrictFixture(V3Fixture):
    def setUp(self):
        super().setUp()
        self.data['discipline'] = 'strict'
        self.step = self.data['steps'][0]
        self.step['effects']['writes'] = ['out.txt']
        self.step['verify'] = [['file', 'out.txt']]
        self.step['test_first_exempt'] = {'kind': 'docs', 'reason': 'Plain text output'}

    def write(self, name='out.txt', text='content\n'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def validate_error(self):
        self.contract.write_text(json.dumps(self.data), encoding='utf-8')
        result = self.call('validate', '--contract', str(self.contract))
        return result.returncode, result.stderr

    def entry(self, step='one'):
        return self.state()['steps'][step]

    def git(self, *args):
        import os
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        environment.update(CLEAN_GIT_ENV)
        result = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def init_repo(self):
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        Path(self.root / '.gitignore').write_text('mission/\ninput.json\n', encoding='utf-8')
        self.git('add', '.gitignore')
        self.git('commit', '-q', '-m', 'base')
